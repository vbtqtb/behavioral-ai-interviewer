"""In-memory interview session.

The shape of each history entry is the same list of dicts the old file store
wrote. The caller keeps that list, sends it back on the next request, and this
object only mutates the copy it was given.
"""

from datetime import datetime
import logging


class InterviewManager:
    """
    Class to manage the conversation history for an interview
    between the user and the LLM interviewer.

    Args:
        session_id: (str) unique interview session key
        interview_id: (str) which TOML interview this session belongs to
    """

    def __init__(self, session_id, interview_id):
        self.session_id = session_id
        self.interview_id = interview_id
        self.history = []
        self.current_state = {}
        self.parameters = {}

    def begin_session(self, parameters):
        """Set starting interview session variables."""
        logging.info("Starting new session '%s'", self.session_id)
        self.history = []
        self.current_state = {
            "order": 0,
            "session_id": self.session_id,
            "topic_idx": 1,
            "question_idx": 1,
            "finish_idx": 1,
            "flagged_messages": 0,
            "terminated": False,
            "summary": "",
            "topic_dags": [],
            "dag_awaiting_feedback": False,
            "dag_pending_question": None,
            "type": "question",
            "content": None,
        }
        self.parameters = parameters

    def resume_session(self, parameters, history):
        """Load a client-supplied history into this Interview object."""
        self.history = history
        assert len(self.history) >= 1
        assert isinstance(self.history[-1], dict)
        assert self.history[-1].get("session_id") == self.session_id
        # Copy so later edits do not rewrite the previous turn until update_session says so.
        self.current_state = self.history[-1].copy()
        self.parameters = parameters
        logging.info("Resumed existing interview session '%s'", self.session_id)

    def get_history(self):
        """Return interview session history."""
        return self.history

    def is_terminated(self):
        """If interview has been terminated."""
        return self.current_state["terminated"]

    def flag_risk(self, message):
        """Flag possible security risk."""
        logging.warning("Flagging message '%s' for possible risk...", message)
        self.current_state["flagged_messages"] += 1

    def flagged_too_often(self):
        """Check if the conversation has been flagged too often."""
        if self.current_state["flagged_messages"] >= self.parameters.get("max_flags_allowed", 3):
            self.terminate("security_flags_exceeded")
            return True
        return False

    def add_chat_to_session(self, message, type):
        """Append a question or answer. The stored turn is a snapshot copy of the state."""
        self.current_state["order"] += 1
        self.current_state["time"] = str(datetime.now())
        self.current_state["content"] = message
        self.current_state["type"] = type
        self.history.append(self.current_state.copy())

    def terminate(self, reason="end_of_interview"):
        """Record termination of interview."""
        self.current_state["terminated"] = True
        logging.info("Terminating interview because: '%s'", reason)

    def update_summary(self, summary):
        """Update summary of prior interview."""
        self.current_state["summary"] = summary

    def get_current_topic(self):
        """Return topic index."""
        return min(int(self.current_state["topic_idx"]), len(self.parameters["interview_plan"]))

    def get_current_topic_question(self):
        """Return question index within topic."""
        return int(self.current_state["question_idx"])

    def get_final_question(self):
        """Get next closing interviewer question. Empty string once they are used up."""
        final_questions = self.parameters.get("closing_questions", [])
        try:
            out = final_questions[int(self.current_state["finish_idx"]) - 1]
        except IndexError:
            out = ""
        else:
            self.current_state["finish_idx"] += 1
        return out

    def update_transition(self, summary):
        """
        Having transitioned, update topic counter (and reset question).

        If the summary agent is enabled, also keep a running summary of
        prior topics for the next prompts.
        """
        self.current_state["question_idx"] = 1
        self.current_state["topic_idx"] += 1
        if self.parameters.get("summary"):
            self.update_summary(summary)

    def update_closing(self):
        """Mark the interview as being in the closing questions."""
        self.current_state["question_idx"] = 99
        self.current_state["topic_idx"] = 99

    def update_probe(self):
        """Having probed within topic, increment the question counter."""
        self.current_state["question_idx"] += 1

    def add_topic_dag(self, dag, topic, svg=""):
        """
        Store an extracted DAG for a completed topic.
        Creates a new list on each call so the snapshot copy in add_chat_to_session
        keeps the DAG list from the moment that turn was stored.
        """
        updated = list(self.current_state.get("topic_dags", []))
        updated.append(
            {
                "topic": topic,
                "dag": dag,
                "svg": svg,
                "accepted": None,
                "correction": None,
            }
        )
        self.current_state["topic_dags"] = updated

    def is_awaiting_dag_feedback(self):
        """True when we are waiting for the user to validate the last DAG."""
        return bool(self.current_state.get("dag_awaiting_feedback", False))

    def set_dag_pending(self, question):
        """Hold a transition question until the user has validated the DAG."""
        self.current_state["dag_awaiting_feedback"] = True
        self.current_state["dag_pending_question"] = question

    def consume_pending_question(self):
        """Return and clear the pending transition question."""
        question = self.current_state.get("dag_pending_question") or ""
        self.current_state["dag_awaiting_feedback"] = False
        self.current_state["dag_pending_question"] = None
        return question

    def resolve_dag_feedback(self, accepted, correction=None):
        """Attach the user's DAG validation response to the last topic_dag entry."""
        dags = list(self.current_state.get("topic_dags", []))
        if dags:
            last = dict(dags[-1])
            last["accepted"] = accepted
            last["correction"] = correction
            dags[-1] = last
            self.current_state["topic_dags"] = dags

    def update_session(self):
        """Write the current state back over the last stored turn.

        Used when a turn changes counters (flags, termination) without adding a
        new message. After this, history[-1] is the live state object.
        """
        self.history[-1] = self.current_state
