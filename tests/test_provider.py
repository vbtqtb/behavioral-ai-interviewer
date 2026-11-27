import base64
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from interviewer.providers import (  # noqa: E402
    LLMProvider,
    ProviderError,
    parse_json_object,
    provider_from_env,
)


class _Response:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    async def text(self):
        return self._body


def _chat(content):
    return json.dumps({"choices": [{"message": {"content": content}}]})


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    def test_fenced_claude_json(self):
        text = 'Here is the graph:\n```json\n{"nodes": [{"id": "1", "label": "rent"}], "edges": []}\n```\n'
        parsed = parse_json_object(text)
        self.assertEqual(parsed["nodes"][0]["label"], "rent")
        self.assertEqual(parsed["edges"], [])

    def test_outermost_object_wins(self):
        parsed = parse_json_object('Sure, here you go:\n{"a": 1, "b": {"c": 2}}\nThanks')
        self.assertEqual(parsed["a"], 1)
        self.assertEqual(parsed["b"]["c"], 2)

    async def test_claude_json_ignores_response_format_and_parses_fences(self):
        seen = {}

        async def fetch(url, method="POST", headers=None, body=None):
            seen["url"] = url
            seen["body"] = json.loads(body)
            return _Response(200, _chat('```json\n{"ok": true}\n```'))

        provider = LLMProvider("claude", "sk-test", fetch=fetch, backoff=0)
        result = await provider.complete_json([{"role": "user", "content": "dag"}], "claude-haiku-5-5", 100, 0)
        self.assertEqual(result, {"ok": True})
        self.assertNotIn("response_format", seen["body"])
        self.assertTrue(seen["url"].endswith("/chat/completions"))

    async def test_openai_json_requests_json_object(self):
        seen = {}

        async def fetch(url, method="POST", headers=None, body=None):
            seen["body"] = json.loads(body)
            seen["auth"] = headers["Authorization"]
            return _Response(200, _chat('{"ok": true}'))

        provider = LLMProvider("openai", "sk-test", fetch=fetch, backoff=0)
        result = await provider.complete_json([{"role": "user", "content": "dag"}], "gpt-4o", 100, 0)
        self.assertEqual(result["ok"], True)
        self.assertEqual(seen["body"]["response_format"], {"type": "json_object"})
        self.assertEqual(seen["auth"], "Bearer sk-test")

    async def test_retries_on_500_then_succeeds(self):
        calls = {"n": 0}

        async def fetch(url, method="POST", headers=None, body=None):
            calls["n"] += 1
            if calls["n"] < 3:
                return _Response(500, "unavailable")
            return _Response(200, _chat("  a question  "))

        provider = LLMProvider("gemini", "gem-key", fetch=fetch, backoff=0)
        text = await provider.complete([{"role": "user", "content": "hi"}], "gemini-2.5-flash-lite", 50, 0)
        self.assertEqual(text, "a question")
        self.assertEqual(calls["n"], 3)

    async def test_auth_failure_is_not_retried(self):
        calls = {"n": 0}

        async def fetch(url, method="POST", headers=None, body=None):
            calls["n"] += 1
            return _Response(401, '{"error": {"message": "invalid api key"}}')

        provider = LLMProvider("openai", "sk-fake", fetch=fetch, backoff=0)
        with self.assertRaises(ProviderError) as caught:
            await provider.complete([{"role": "user", "content": "hi"}], "gpt-4o", 50, 0)
        self.assertIn("API key", str(caught.exception))
        self.assertIn("401", str(caught.exception))
        self.assertNotIn("Traceback", str(caught.exception))
        self.assertEqual(calls["n"], 1)

    async def test_whisper_multipart_reaches_the_audio_endpoint(self):
        seen = {}

        async def fetch(url, method="POST", headers=None, body=None):
            seen["url"] = url
            seen["type"] = headers["Content-Type"]
            seen["body"] = body
            return _Response(200, json.dumps({"text": "hello there"}))

        provider = LLMProvider("openai", "sk-test", fetch=fetch, backoff=0)
        audio = base64.b64encode(b"fake-webm").decode("ascii")
        text = await provider.transcribe(audio)
        self.assertEqual(text, "hello there")
        self.assertTrue(seen["url"].endswith("/audio/transcriptions"))
        self.assertIn("multipart/form-data", seen["type"])
        self.assertIn(b"whisper-1", seen["body"])
        self.assertIn(b'filename="audio.webm"', seen["body"])
        self.assertIn(b"fake-webm", seen["body"])

    async def test_gemini_transcribe_sends_inline_audio(self):
        seen = {}

        async def fetch(url, method="POST", headers=None, body=None):
            seen["url"] = url
            seen["body"] = json.loads(body)
            return _Response(
                200,
                json.dumps({"candidates": [{"content": {"parts": [{"text": "spoken words"}]}}]}),
            )

        provider = LLMProvider("gemini", "gem-key", fetch=fetch, backoff=0)
        text = await provider.transcribe(base64.b64encode(b"audio").decode("ascii"))
        self.assertEqual(text, "spoken words")
        self.assertIn(":generateContent?key=gem-key", seen["url"])
        self.assertNotIn("openai", seen["url"])
        inline = seen["body"]["contents"][0]["parts"][0]["inlineData"]
        self.assertEqual(inline["mimeType"], "audio/webm")
        self.assertEqual(base64.b64decode(inline["data"]), b"audio")

    async def test_claude_voice_is_rejected(self):
        async def fetch(url, method="POST", headers=None, body=None):
            raise AssertionError("Claude transcription must not call the network")

        provider = LLMProvider("claude", "sk-ant", fetch=fetch, backoff=0)
        with self.assertRaises(ProviderError) as caught:
            await provider.transcribe(base64.b64encode(b"audio").decode("ascii"))
        self.assertIn("Voice input is not supported with Claude", str(caught.exception))

    async def test_moderation_only_for_openai(self):
        async def fetch(url, method="POST", headers=None, body=None):
            raise AssertionError("Gemini moderation must not call the network")

        gemini = LLMProvider("gemini", "gem-key", fetch=fetch, backoff=0)
        self.assertFalse(await gemini.moderate_text("anything"))

        async def openai_fetch(url, method="POST", headers=None, body=None):
            self.assertTrue(url.endswith("/moderations"))
            return _Response(200, json.dumps({"results": [{"flagged": True}]}))

        openai = LLMProvider("openai", "sk-test", fetch=openai_fetch, backoff=0)
        self.assertTrue(await openai.moderate_text("something risky"))

    def test_missing_key_names_the_secret(self):
        with self.assertRaises(ProviderError) as caught:
            LLMProvider("openai", "")
        self.assertIn("OPENAI_API_KEY", str(caught.exception))


class EnvTextTests(unittest.TestCase):
    def test_none_and_blank_mean_unset(self):
        from types import SimpleNamespace
        from interviewer.errors import env_text

        env = SimpleNamespace(A="none", B="  ", C=" NONE ", D=" key ")
        self.assertIsNone(env_text(env, "A"))
        self.assertIsNone(env_text(env, "B"))
        self.assertIsNone(env_text(env, "C"))
        self.assertIsNone(env_text(env, "MISSING"))
        self.assertEqual(env_text(env, "D"), "key")

    def test_provider_ignores_none_placeholders(self):
        from types import SimpleNamespace

        env = SimpleNamespace(LLM_PROVIDER="gemini", GEMINI_API_KEY="real", OPENAI_API_KEY="none", LLM_MODEL="none")
        provider = provider_from_env(env)
        self.assertEqual(provider.provider_name, "gemini")
        self.assertIsNone(provider.model_override)


if __name__ == "__main__":
    unittest.main()
