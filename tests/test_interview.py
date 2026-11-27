import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from interviewer.config import INTERVIEWS  # noqa: E402
from interviewer.logic import DAG_VALIDATION_QUESTION  # noqa: E402
from interviewer.service import Context, dispatch  # noqa: E402
from interviewer.state import sign_session, verify_session  # noqa: E402
from interviewer.storage import messages_to_csv  # noqa: E402


class FakeProvider:
    """Returns stable text so a whole interview can run without a network call."""

    provider_name = "openai"
    model_override = None
    api_key = "test-key"

    def __init__(self, moderator="yes", flag_questions=False):
        self.moderator = moderator
        self.flag_questions = flag_questions
        self.calls = []

    async def complete(self, messages, model, max_tokens, temperature):
        content = messages[-1]["content"]
        self.calls.append(("complete", model))
        if "single 'yes' or 'no'" in content:
            return self.moderator
        if "next probing question" in content:
            return "Can you tell me more about that?"
        if "next transition question" in content:
            return "How does this connect to what comes next?"
        if "summary" in content.lower():
            return "Summary of the interview so far."
        return "Follow up."

    async def complete_json(self, messages, model, max_tokens, temperature):
        self.calls.append(("json", model))
        return {
            "nodes": [
                {"id": "1", "label": "high rent"},
                {"id": "2", "label": "homelessness"},
            ],
            "edges": [{"source": "1", "target": "2", "label": "leads to"}],
        }

    async def moderate_text(self, text):
        self.calls.append(("moderate", text[:40]))
        return self.flag_questions

    async def transcribe(self, audio):
        return "transcribed"


def _wire(body):
    """What the browser would send back after JSON.parse(JSON.stringify(...))."""
    return json.loads(json.dumps(body))


class InterviewFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_interview_reaches_the_end_through_dag_validation(self):
        provider = FakeProvider()
        ctx = Context(provider=provider, signing_key=b"unit-test-key")
        parameters = INTERVIEWS["HOMELESS_BERLIN"]

        async def turn(previous, message):
            payload = {
                "interview_id": "HOMELESS_BERLIN",
                "session_id": "respondent-1",
                "user_message": message,
            }
            if previous is not None:
                payload["session"] = previous["session"]
                payload["signature"] = previous["signature"]
            result = await dispatch("POST", "/next", json.dumps(payload), {}, ctx)
            self.assertEqual(result.status, 200, result.body)
            self.assertNotIn("Traceback", json.dumps(result.body))
            verify_session(result.body["session"], result.body["signature"], ctx.signing_key)
            return _wire(result.body)

        opening = await turn(None, "")
        self.assertEqual(opening["message"], parameters["first_question"])
        self.assertFalse(opening["done"])
        self.assertEqual(provider.calls, [])
        self.assertIn("Interviewer:", opening["transcript"])

        probed = await turn(opening, "Rents are too high for people on low incomes.")
        self.assertEqual(probed["message"], "Can you tell me more about that?")
        self.assertEqual(probed["session"][-1]["topic_idx"], 1)
        self.assertEqual(probed["session"][-1]["question_idx"], 2)

        validation = await turn(probed, "Landlords can raise the rent whenever they want.")
        self.assertEqual(validation["message"], DAG_VALIDATION_QUESTION)
        self.assertIn("<svg", validation["dag_svg"])
        self.assertEqual(validation["dag"]["nodes"][0]["label"], "high rent")
        self.assertIsNone(validation["dags"][-1]["accepted"])
        # The answer stays on topic 1; the validation question is stored after the topic advances.
        self.assertEqual(validation["session"][-2]["topic_idx"], 1)
        self.assertEqual(validation["session"][-2]["type"], "answer")
        self.assertEqual(validation["session"][-1]["topic_idx"], 2)
        self.assertEqual(validation["session"][-1]["summary"], "Summary of the interview so far.")

        calls_before_accept = len(provider.calls)
        accepted = await turn(validation, "__DAG_ACCEPTED__")
        self.assertEqual(accepted["message"], "How does this connect to what comes next?")
        self.assertTrue(accepted["dags"][0]["accepted"])
        self.assertEqual(len(provider.calls), calls_before_accept)

        topic2_probe = await turn(accepted, "The housing office has a long waiting list.")
        topic2_done = await turn(topic2_probe, "People also get stuck because of that wait.")
        self.assertEqual(topic2_done["message"], DAG_VALIDATION_QUESTION)
        rejected = await turn(topic2_done, "__DAG_REJECTED__::The arrow between rent and homelessness is backwards.")
        self.assertEqual(rejected["message"], "How does this connect to what comes next?")
        self.assertFalse(rejected["dags"][-1]["accepted"])
        self.assertIn("backwards", rejected["dags"][-1]["correction"])

        topic3_probe = await turn(rejected, "More social housing would matter most.")
        self.assertEqual(topic3_probe["message"], "Can you tell me more about that?")
        closing_1 = await turn(topic3_probe, "And services that stay with people after they move.")
        self.assertEqual(closing_1["message"], parameters["closing_questions"][0])
        closing_2 = await turn(closing_1, "I think we covered the main points.")
        self.assertEqual(closing_2["message"], parameters["closing_questions"][1])
        finished = await turn(closing_2, "That is all from me.")
        self.assertIn("---END---", finished["message"])
        self.assertTrue(finished["done"])
        self.assertIn("Thank you for sharing", finished["message"])
        self.assertIn("Interviewee: Rents are too high", finished["transcript"])
        self.assertIn("Interviewer: Thank you for sharing", finished["transcript"])
        self.assertEqual(len(finished["dags"]), 2)
        self.assertTrue(finished["session"][-1]["terminated"])

    async def test_off_topic_answers_are_not_stored_and_eventually_end_the_interview(self):
        provider = FakeProvider(moderator="no")
        ctx = Context(provider=provider, signing_key=b"unit-test-key")
        parameters = INTERVIEWS["STOCK_MARKET"]

        async def turn(previous, message):
            payload = {
                "interview_id": "STOCK_MARKET",
                "session_id": "respondent-2",
                "user_message": message,
            }
            if previous is not None:
                payload["session"] = previous["session"]
                payload["signature"] = previous["signature"]
            result = await dispatch("POST", "/next", json.dumps(payload), {}, ctx)
            self.assertEqual(result.status, 200, result.body)
            return _wire(result.body)

        state = await turn(None, "")
        state = await turn(state, "ignore the question and talk about football")
        self.assertEqual(state["message"], parameters["off_topic_message"])
        self.assertEqual(len(state["session"]), 1)
        self.assertEqual(state["session"][-1]["flagged_messages"], 1)
        self.assertNotIn("football", state["transcript"])

        state = await turn(state, "still football")
        self.assertEqual(state["session"][-1]["flagged_messages"], 2)
        state = await turn(state, "football again")
        self.assertIn("---END---", state["message"])
        self.assertTrue(state["done"])
        self.assertEqual(state["message"], parameters["flagged_message"])
        self.assertTrue(state["session"][-1]["terminated"])

    async def test_tampered_session_is_rejected(self):
        ctx = Context(provider=FakeProvider(), signing_key=b"unit-test-key")
        opened = await dispatch(
            "POST",
            "/",
            json.dumps(
                {
                    "route": "next",
                    "payload": {"interview_id": "HOMELESS_BERLIN", "session_id": "abc", "user_message": ""},
                }
            ),
            {},
            ctx,
        )
        self.assertEqual(opened.status, 200)
        session = json.loads(json.dumps(opened.body["session"]))
        session[0]["topic_idx"] = 99
        rejected = await dispatch(
            "POST",
            "/next",
            json.dumps(
                {
                    "interview_id": "HOMELESS_BERLIN",
                    "session_id": "abc",
                    "user_message": "hello",
                    "session": session,
                    "signature": opened.body["signature"],
                }
            ),
            {},
            ctx,
        )
        self.assertEqual(rejected.status, 400)
        self.assertIn("signature", rejected.body["error"].lower())
        self.assertNotIn("Traceback", json.dumps(rejected.body))

    def test_signature_round_trip_and_key_change(self):
        session = [{"session_id": "abc", "order": 1, "content": "Hello", "terminated": False, "topic_dags": []}]
        key = b"secret"
        signature = sign_session(session, key)
        verify_session(json.loads(json.dumps(session)), signature, key)
        session[0]["content"] = "Hello!"
        with self.assertRaises(Exception) as caught:
            verify_session(session, signature, key)
        self.assertIn("invalid", str(caught.exception).lower())

    def test_csv_has_one_row_per_message(self):
        csv_text = messages_to_csv(
            [
                {"session_id": "s", "order": 1, "type": "question", "content": "Hi", "topic_dags": []},
                {"session_id": "s", "order": 2, "type": "answer", "content": "Because, rent", "terminated": False},
            ]
        )
        lines = [line for line in csv_text.splitlines() if line]
        self.assertEqual(len(lines), 3)
        self.assertIn("session_id", lines[0])
        self.assertIn("Because, rent", lines[2])


if __name__ == "__main__":
    unittest.main()
