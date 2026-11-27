"""One async chat-completions client for OpenAI, Gemini, and Claude.

Nothing from `workers` or `js` is imported at module import time, so the unit
tests can load this file with plain CPython and pass in a fake fetch.
"""

import asyncio
import base64
import json
import logging
import re
from secrets import token_hex

from interviewer.config import DEFAULT_MODELS
from interviewer.errors import ClientError, env_text

log = logging.getLogger(__name__)

BASE_URLS = {
    "openai": "https://api.openai.com/v1/",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "claude": "https://api.anthropic.com/v1/",
}

KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}

WHISPER_MODEL = "whisper-1"
TRANSCRIBE_PROMPT = "Transcribe the audio. Return only the transcription text, nothing else."


class ProviderError(Exception):
    """The model provider failed. `status` is the HTTP status for our own response."""

    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def parse_json_object(text):
    """Parse a JSON object from model text, stripping ``` fences and surrounding prose."""
    if not isinstance(text, str):
        raise ProviderError("The model did not return text that could be parsed as JSON.")
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ProviderError("The model response did not contain a JSON object.")
    try:
        value = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ProviderError("The model response was not valid JSON.") from exc
    if not isinstance(value, dict):
        raise ProviderError("The model JSON response was not an object.")
    return value


def decode_audio(audio):
    """Decode the base64 audio string the browser recorded."""
    if not isinstance(audio, str) or not audio.strip():
        raise ClientError("Missing audio.")
    raw = audio.strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    raw = "".join(raw.split())
    padding = (-len(raw)) % 4
    try:
        return base64.b64decode(raw + ("=" * padding), validate=False)
    except Exception as exc:
        raise ClientError("Audio payload is not valid base64.") from exc


def multipart_form(fields, files):
    """Build a multipart/form-data body. Returns (bytes, boundary)."""
    boundary = "----aiint" + token_hex(8)
    chunks = []
    for name, value in fields:
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(value.encode("utf-8") if isinstance(value, str) else value)
        chunks.append(b"\r\n")
    for name, filename, content_type, data in files:
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        chunks.append(data)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


async def _default_fetch(url, method="GET", headers=None, body=None):
    # Imported lazily so `import interviewer.providers` works without the Workers runtime.
    from workers import fetch as worker_fetch

    kwargs = {"method": method, "headers": headers or {}}
    if body is not None:
        kwargs["body"] = body
    return await worker_fetch(url, **kwargs)


def _completion_text(raw):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError("The language model returned a non-JSON response.") from exc
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("The language model response had no message text.") from exc
    if content is None:
        return ""
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "".join(parts)
    return str(content)


class LLMProvider:
    """Chat completions against an OpenAI-compatible endpoint."""

    def __init__(self, provider_name, api_key, fetch=None, model_override=None, backoff=0.25):
        name = (provider_name or "").strip().lower()
        if name not in BASE_URLS:
            raise ProviderError(
                f"Unknown LLM provider '{provider_name}'. Use openai, gemini, or claude.",
                status=500,
            )
        if not api_key:
            raise ProviderError(
                f"Missing API key for provider '{name}'. Set the {KEY_ENV[name]} secret.",
                status=500,
            )
        self.provider_name = name
        self.api_key = api_key
        self.model_override = model_override or None
        self.backoff = backoff
        self._fetch = fetch or _default_fetch
        self.base_url = BASE_URLS[name]

    def _headers(self, content_type="application/json"):
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    async def _post(self, url, headers, body):
        """POST once, then retry up to twice on HTTP 429 or 5xx."""
        last_status = 0
        last_body = ""
        for attempt in range(3):
            response = await self._fetch(url, method="POST", headers=headers, body=body)
            status = int(response.status)
            text = await response.text()
            if status < 400:
                return text
            last_status, last_body = status, text
            if status == 429 or status >= 500:
                if attempt < 2:
                    await asyncio.sleep(self.backoff * (attempt + 1))
                    continue
            break
        self._raise(last_status, last_body)

    def _raise(self, status, body):
        log.error("LLM HTTP %s from %s: %s", status, self.provider_name, (body or "")[:500])
        if status in (401, 403):
            raise ProviderError(
                f"The language model rejected the API key (HTTP {status}). "
                f"Check the {KEY_ENV[self.provider_name]} secret.",
                status=502,
            )
        raise ProviderError(f"The language model request failed (HTTP {status}).", status=502)

    async def complete(self, messages, model, max_tokens, temperature):
        """Run a chat completion and return the response text."""
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
        }
        raw = await self._post(self.base_url + "chat/completions", self._headers(), json.dumps(body))
        return _completion_text(raw).strip("\n\" '''")

    async def complete_json(self, messages, model, max_tokens, temperature):
        """Run a chat completion and return a parsed JSON object.

        OpenAI and Gemini get `response_format: json_object`. Claude's compatible
        endpoint does not honour that reliably, so the text is parsed instead.
        """
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
        }
        if self.provider_name != "claude":
            body["response_format"] = {"type": "json_object"}
        raw = await self._post(self.base_url + "chat/completions", self._headers(), json.dumps(body))
        return parse_json_object(_completion_text(raw))

    async def moderate_text(self, text):
        """True when OpenAI's moderation endpoint flags the text. Other providers return False."""
        if self.provider_name != "openai":
            return False
        body = {"model": "omni-moderation-latest", "input": text}
        raw = await self._post(self.base_url + "moderations", self._headers(), json.dumps(body))
        try:
            data = json.loads(raw)
            return bool(data["results"][0]["flagged"])
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("The moderation endpoint returned an unexpected response.") from exc

    async def transcribe(self, audio):
        """Transcribe base64 audio. Claude has no speech endpoint in this setup."""
        if self.provider_name == "claude":
            raise ProviderError(
                "Voice input is not supported with Claude. Set LLM_PROVIDER to openai or gemini.",
                status=400,
            )
        audio_bytes = decode_audio(audio)
        if self.provider_name == "gemini":
            return await self._transcribe_gemini(audio_bytes)
        return await self._transcribe_openai(audio_bytes)

    async def _transcribe_openai(self, audio_bytes):
        body, boundary = multipart_form(
            [("model", WHISPER_MODEL), ("language", "en")],
            [("file", "audio.webm", "audio/webm", audio_bytes)],
        )
        raw = await self._post(
            self.base_url + "audio/transcriptions",
            self._headers(f"multipart/form-data; boundary={boundary}"),
            body,
        )
        try:
            data = json.loads(raw)
            text = data["text"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ProviderError("The transcription endpoint returned an unexpected response.") from exc
        return str(text).strip()

    async def _transcribe_gemini(self, audio_bytes):
        model = self.model_override or DEFAULT_MODELS["gemini"]
        # Native generateContent, not the OpenAI-compatible route: it accepts inline audio.
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + model
            + ":generateContent?key="
            + self.api_key
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "audio/webm",
                                "data": base64.b64encode(audio_bytes).decode("ascii"),
                            }
                        },
                        {"text": TRANSCRIBE_PROMPT},
                    ]
                }
            ]
        }
        raw = await self._post(url, {"Content-Type": "application/json"}, json.dumps(payload))
        try:
            data = json.loads(raw)
            parts = data["candidates"][0]["content"]["parts"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Gemini transcription returned an unexpected response.") from exc
        texts = [str(part.get("text", "")) for part in parts if isinstance(part, dict) and part.get("text")]
        return "\n".join(texts).strip()


def provider_from_env(env, fetch=None, backoff=0.25):
    """Build the provider selected by LLM_PROVIDER. Raises ProviderError if the key is missing."""
    name = env_text(env, "LLM_PROVIDER") or "openai"
    override = env_text(env, "LLM_MODEL")
    tentative = name.lower()
    env_name = KEY_ENV.get(tentative)
    key = env_text(env, env_name) if env_name else None
    return LLMProvider(tentative, key, fetch=fetch, model_override=override, backoff=backoff)
