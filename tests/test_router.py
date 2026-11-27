import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from interviewer.providers import LLMProvider  # noqa: E402
from interviewer.service import Context, dispatch  # noqa: E402


class RouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ctx = Context(provider=LLMProvider("openai", "sk-test", fetch=FakeFetch(), backoff=0), signing_key=b"k")

    async def test_health_and_interview_list(self):
        health = await dispatch("GET", "/healthcheck", "", {}, self.ctx)
        self.assertEqual(health.status, 200)
        self.assertEqual(health.body, "ok")
        root = await dispatch("GET", "/", "", {}, self.ctx)
        self.assertEqual(root.body, "Running!")
        listing = await dispatch("GET", "/interviews", "", {}, self.ctx)
        self.assertEqual(listing.body["interviews"], ["HOMELESS_BERLIN", "STOCK_MARKET"])

    async def test_dispatcher_unknown_route(self):
        result = await dispatch(
            "POST",
            "/",
            json.dumps({"route": "retrieve", "payload": {}}),
            {},
            self.ctx,
        )
        self.assertEqual(result.status, 400)
        self.assertIn("Unknown route", result.body["error"])
        self.assertNotIn("Traceback", result.body["error"])

    async def test_dispatcher_next_and_direct_next(self):
        via_root = await dispatch(
            "POST",
            "/",
            json.dumps(
                {
                    "route": "next",
                    "payload": {"interview_id": "STOCK_MARKET", "session_id": "u1", "user_message": ""},
                }
            ),
            {},
            self.ctx,
        )
        self.assertEqual(via_root.status, 200)
        self.assertIn("stock", via_root.body["message"].lower())
        self.assertTrue(via_root.body["signature"])
        direct = await dispatch(
            "POST",
            "/next",
            json.dumps({"interview_id": "HOMELESS_BERLIN", "user_message": ""}),
            {},
            self.ctx,
        )
        self.assertEqual(direct.status, 200)
        self.assertTrue(direct.body["session_id"])
        self.assertFalse(direct.body["done"])

    async def test_transcribe_route(self):
        result = await dispatch(
            "POST",
            "/",
            json.dumps({"route": "transcribe", "payload": {"audio": "YWI="}}),
            {},
            self.ctx,
        )
        self.assertEqual(result.status, 200, result.body)
        self.assertEqual(result.body["transcription"], "hello there")

    async def test_provider_auth_error_is_clean_json(self):
        fetch = FakeFetch(status=401, body='{"error":{"message":"bad key"}}')
        ctx = Context(provider=LLMProvider("openai", "sk-fake", fetch=fetch, backoff=0), signing_key=b"k")
        opened = await dispatch(
            "POST",
            "/next",
            json.dumps({"interview_id": "HOMELESS_BERLIN", "session_id": "u", "user_message": ""}),
            {},
            ctx,
        )
        self.assertEqual(opened.status, 200)
        failed = await dispatch(
            "POST",
            "/next",
            json.dumps(
                {
                    "interview_id": "HOMELESS_BERLIN",
                    "session_id": "u",
                    "user_message": "People cannot afford rent.",
                    "session": opened.body["session"],
                    "signature": opened.body["signature"],
                }
            ),
            {},
            ctx,
        )
        self.assertEqual(failed.status, 502)
        self.assertIn("API key", failed.body["error"])
        self.assertIn("401", failed.body["error"])
        self.assertNotIn("Traceback", json.dumps(failed.body))

    async def test_limits_and_pages(self):
        huge = await dispatch("POST", "/next", "x" * (1_000_001), {}, self.ctx)
        self.assertEqual(huge.status, 413)
        long_message = await dispatch(
            "POST",
            "/next",
            json.dumps({"interview_id": "HOMELESS_BERLIN", "user_message": "a" * 5001}),
            {},
            self.ctx,
        )
        self.assertEqual(long_message.status, 400)
        page = await dispatch("GET", "/test/HOMELESS_BERLIN", "", {}, self.ctx)
        self.assertEqual(page.status, 200)
        self.assertIn("chatArea", page.body)
        self.assertIn("HOMELESS_BERLIN", page.body)
        missing = await dispatch("GET", "/test/NOT_A_REAL_INTERVIEW", "", {}, self.ctx)
        self.assertEqual(missing.status, 404)
        export = await dispatch("GET", "/export", "", {"password": ["nope"]}, self.ctx)
        self.assertEqual(export.status, 404)

    async def test_options_is_not_a_post(self):
        # CORS preflight is answered by the worker entry, not by dispatch.
        result = await dispatch("PUT", "/next", "{}", {}, self.ctx)
        self.assertEqual(result.status, 405)


class FakeFetch:
    def __init__(self, status=200, body=None):
        self.status = status
        self.body = body or chat_body("hello there")
        self.calls = 0

    async def __call__(self, url, method="POST", headers=None, body=None):
        self.calls += 1
        if "audio/transcriptions" in url:
            return _Response(200, json.dumps({"text": "hello there"}))
        return _Response(self.status, self.body)


class _Response:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    async def text(self):
        return self._body


def chat_body(content):
    return json.dumps({"choices": [{"message": {"content": content}}]})


if __name__ == "__main__":
    unittest.main()
