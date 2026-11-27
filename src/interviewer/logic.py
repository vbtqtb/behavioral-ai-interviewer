"""Turn-by-turn interview flow.

This follows the previous Flask app: moderate the answer, record it, then
either probe, transition (optionally extracting a DAG and waiting for the
respondent to accept it), or ask the closing questions.
"""

import logging
import time

from interviewer.agent import LLMAgent
from interviewer.auxiliary import transcript_text
from interviewer.errors import ClientError
from interviewer.manager import InterviewManager
from interviewer.svg_generator import dag_to_svg

log = logging.getLogger(__name__)

DAG_VALIDATION_QUESTION = (
    "Does this graph match your mental model of the topic? "
    "Please answer Yes or No. "
    "If No, you can briefly explain what is incorrect."
)


def _result(interview, message, dag=None, dag_svg=""):
    """Fields the browser and Qualtrics export need after every turn."""
    history = interview.history
    dags = list(interview.current_state.get("topic_dags") or [])
    return {
        "session_id": interview.session_id,
        "interview_id": interview.interview_id,
        "message": message,
        "dag": dag or {},
        "dag_svg": dag_svg or "",
        "session": history,
        "done": "---END---" in (message or ""),
        "transcript": transcript_text(history, message),
        "dags": dags,
    }


def begin_interview_session(session_id, interview_id, parameters):
    """Return the response that opens a new interview session."""
    interview = InterviewManager(session_id, interview_id)
    interview.begin_session(parameters)
    message = parameters["first_question"]
    interview.add_chat_to_session(message, type="question")
    log.info("Beginning %s interview session '%s'", interview_id, session_id)
    return _result(interview, message)


async def next_question(session_id, interview_id, user_message, session, parameters, provider):
    """
    Process the user message and generate the interviewer's next turn.

    Args:
        session_id: unique interview session ID
        interview_id: which interview TOML to follow
        user_message: interviewee response (ignored when `session` is empty)
        session: prior history list, or None to start
        parameters: validated interview config
        provider: async LLM provider
    Returns:
        dict with message, session, done, transcript, and any DAG for this turn
    """
    if not session:
        return begin_interview_session(session_id, interview_id, parameters)

    interview = InterviewManager(session_id, interview_id)
    try:
        interview.resume_session(parameters, session)
    except AssertionError as exc:
        raise ClientError("Session could not be resumed. Start again without a session.") from exc

    if interview.is_terminated():
        return _result(interview, parameters["termination_message"])

    # The browser sends these instead of a normal answer while the DAG is on screen.
    if interview.is_awaiting_dag_feedback():
        message = user_message or ""
        if message.startswith("__DAG_ACCEPTED__"):
            interview.resolve_dag_feedback(accepted=True)
        elif message.startswith("__DAG_REJECTED__::"):
            correction = message[len("__DAG_REJECTED__::") :]
            interview.resolve_dag_feedback(accepted=False, correction=correction)
        else:
            interview.update_session()
            return _result(interview, DAG_VALIDATION_QUESTION)

        pending_question = interview.consume_pending_question()
        interview.add_chat_to_session(pending_question, type="question")
        return _result(interview, pending_question)

    agent = LLMAgent(provider)
    agent.load_parameters(parameters)

    started = time.time()
    log.info(
        "[%s] request received — topic %s, question %s",
        session_id,
        interview.get_current_topic(),
        interview.get_current_topic_question(),
    )

    if parameters.get("moderate_answers") and parameters.get("moderator"):
        on_topic = await agent.review_answer(user_message, interview.get_history())
        log.info("[%s] moderation done (%.2fs)", session_id, time.time() - started)
        if not on_topic:
            interview.flag_risk(user_message)
        if interview.flagged_too_often():
            interview.update_session()
            return _result(interview, parameters["flagged_message"])
        # Off-topic, but not yet over the flag limit: do not store the message.
        if not on_topic:
            interview.update_session()
            return _result(interview, parameters["off_topic_message"])

    # Flagged messages are not added to the history. Only answers that passed are.
    interview.add_chat_to_session(user_message, type="answer")

    num_topics = len(parameters["interview_plan"])
    current_topic_idx = interview.get_current_topic()
    on_last_topic = current_topic_idx == num_topics
    log.info("On topic %s/%s...", current_topic_idx, num_topics)

    current_question_idx = interview.get_current_topic_question()
    num_questions = parameters["interview_plan"][current_topic_idx - 1]["length"]
    on_last_question = current_question_idx >= num_questions
    log.info("On question %s/%s...", current_question_idx, num_questions)

    dag = {}
    dag_svg = ""
    if on_last_topic and on_last_question:
        reply = interview.get_final_question()
        interview.update_closing()
        if not reply:
            interview.terminate()
            interview.update_session()
            return _result(interview, parameters["end_of_interview_message"])
    elif on_last_question:
        if parameters.get("dag"):
            current_topic = parameters["interview_plan"][current_topic_idx - 1]["topic"]
            log.info("[%s] extracting DAG for topic '%s'...", session_id, current_topic)
            dag = await agent.extract_dag(current_topic, current_topic_idx, interview.get_history())
            log.info("[%s] DAG done (%.2fs)", session_id, time.time() - started)
            dag_svg = dag_to_svg(dag)
            interview.add_topic_dag(dag, current_topic, svg=dag_svg)
        log.info("[%s] transitioning topic...", session_id)
        transition_question, summary = await agent.transition_topic(interview.get_history())
        log.info("[%s] transition done (%.2fs)", session_id, time.time() - started)
        interview.update_transition(summary)

        # Pause on the graph before asking the transition question.
        if dag and dag_svg:
            interview.set_dag_pending(transition_question)
            interview.add_chat_to_session(DAG_VALIDATION_QUESTION, type="question")
            return _result(interview, DAG_VALIDATION_QUESTION, dag=dag, dag_svg=dag_svg)
        reply = transition_question
    else:
        log.info("[%s] probing within topic...", session_id)
        reply = await agent.probe_within_topic(interview.get_history())
        log.info("[%s] probe done (%.2fs)", session_id, time.time() - started)
        interview.update_probe()

    log.info("[%s] total request time: %.2fs", session_id, time.time() - started)
    interview.add_chat_to_session(reply, type="question")

    if parameters.get("moderate_questions"):
        flagged_question = await agent.review_question(reply)
        if flagged_question:
            interview.terminate(reason="question_flagged")
            interview.update_session()
            return _result(interview, parameters["end_of_interview_message"])

    return _result(interview, reply)
