"""HTTP routing that does not import the Workers runtime.

`entry.py` turns the result into a Workers Response. Tests call `dispatch` directly.
"""

import json
import logging
import uuid
from urllib.parse import unquote

from interviewer.config import INTERVIEWS
from interviewer.errors import ClientError, env_text
from interviewer.logic import next_question
from interviewer.providers import ProviderError, provider_from_env
from interviewer.state import SessionError, make_signing_key, secrets_equal, sign_session, verify_session
from interviewer.storage import load_messages, messages_to_csv, save_session
from interviewer.test_page import render_test_page

log = logging.getLogger(__name__)

MAX_BODY_BYTES = 1_000_000
MAX_MESSAGE_CHARS = 5000
MAX_SESSION_ENTRIES = 300
MAX_SESSION_ID_CHARS = 200

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


class HttpResult:
    """What the worker should send back. `body` is a dict for JSON, or text otherwise."""

    def __init__(self, status, body, content_type="application/json", headers=None):
        self.status = status
        self.body = body
        self.content_type = content_type
        self.headers = headers or {}


class Context:
    """Per-request dependencies. Tests pass a provider and signing key directly."""

    def __init__(self, env=None, provider=None, interviews=None, signing_key=None, db=None, admin_password=None):
        self.env = env
        self.provider = provider
        self.interviews = interviews if interviews is not None else INTERVIEWS
        self.signing_key = signing_key
        self.db = db
        self.admin_password = admin_password


def _normalise_path(path):
    if not path:
        return "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return path


def _parse_json_body(body):
    if body is None or body == "":
        raise ClientError("Expected a JSON body.")
    size = len(body.encode("utf-8"))
    if size > MAX_BODY_BYTES:
        raise ClientError("Request body is larger than 1 MB.", status=413)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise ClientError("Request body is not valid JSON.")
    if not isinstance(data, dict):
        raise ClientError("Request body must be a JSON object.")
    return data


def _session_id_from(payload):
    session_id = payload.get("session_id")
    if session_id is None or session_id == "":
        session_id = payload.get("user_id")
    if session_id is None or session_id == "":
        # Generated only while handling a request. Import-time randomness is not allowed.
        session_id = str(uuid.uuid4())
    if not isinstance(session_id, str):
        session_id = str(session_id)
    if len(session_id) > MAX_SESSION_ID_CHARS:
        raise ClientError("session_id is too long.")
    return session_id


def _checked_session(payload, session_id):
    session = payload.get("session", None)
    if session is None:
        return None
    if not isinstance(session, list):
        raise ClientError("session must be a list.")
    if len(session) == 0:
        return None
    if len(session) > MAX_SESSION_ENTRIES:
        raise ClientError(f"session is longer than {MAX_SESSION_ENTRIES} messages.")
    for index, item in enumerate(session):
        if not isinstance(item, dict):
            raise ClientError(f"session[{index}] must be an object.")
    if session[-1].get("session_id") != session_id:
        raise ClientError("session does not match session_id.")
    return session


def _checked_message(payload, continuing):
    message = payload.get("user_message", "")
    if message is None:
        message = ""
    if not isinstance(message, str):
        raise ClientError("user_message must be a string.")
    if len(message) > MAX_MESSAGE_CHARS:
        raise ClientError(f"user_message is longer than {MAX_MESSAGE_CHARS} characters.")
    if continuing and "user_message" not in payload:
        raise ClientError("user_message is required when continuing a session.")
    return message


async def _ensure_llm(ctx):
    """Create the provider and signing key on the first turn that needs them."""
    if ctx.provider is not None and ctx.signing_key is not None:
        return
    if ctx.provider is None:
        if ctx.env is None:
            raise ProviderError("No language-model provider is configured.", status=500)
        ctx.provider = provider_from_env(ctx.env)
    if ctx.signing_key is None:
        secret = None
        if ctx.env is not None:
            secret = env_text(ctx.env, "SESSION_SECRET")
        ctx.signing_key = make_signing_key(secret, ctx.provider.api_key)


async def run_next(payload, ctx):
    """Validate one `next` payload, advance the interview, and sign the new session."""
    await _ensure_llm(ctx)
    interview_id = payload.get("interview_id")
    if not isinstance(interview_id, str) or not interview_id.strip():
        raise ClientError("interview_id is required.")
    if interview_id not in ctx.interviews:
        raise ClientError(f"Unknown interview '{interview_id}'.", status=404)

    session_id = _session_id_from(payload)
    session = _checked_session(payload, session_id)
    if session is not None:
        verify_session(session, payload.get("signature"), ctx.signing_key)
    message = _checked_message(payload, continuing=session is not None)

    result = await next_question(
        session_id=session_id,
        interview_id=interview_id,
        user_message=message,
        session=session,
        parameters=ctx.interviews[interview_id],
        provider=ctx.provider,
    )
    result["signature"] = sign_session(result["session"], ctx.signing_key)
    await _backup(ctx, result)
    return result


async def run_transcribe(payload, ctx):
    """Transcribe one audio clip. No session is involved."""
    await _ensure_llm(ctx)
    audio = payload.get("audio")
    text = await ctx.provider.transcribe(audio)
    return {"transcription": text}


async def _backup(ctx, result):
    """Best-effort D1 upsert. A database problem must not fail the interview."""
    if ctx.db is None:
        return
    try:
        await save_session(
            ctx.db,
            result["session_id"],
            result.get("interview_id") or "",
            result["session"],
            result.get("transcript") or "",
        )
    except Exception:
        log.exception("D1 backup failed for session %s", result.get("session_id"))


async def run_export(query, ctx):
    """CSV of every stored turn. Hidden unless ADMIN_PASSWORD is set and a DB is bound."""
    admin = ctx.admin_password
    if ctx.env is not None and not admin:
        admin = env_text(ctx.env, "ADMIN_PASSWORD")
    db = ctx.db
    if ctx.env is not None and db is None:
        db = getattr(ctx.env, "DB", None)
    if not admin or db is None:
        return HttpResult(404, {"error": "Not found"})
    supplied = ""
    if query:
        values = query.get("password") or [""]
        supplied = values[0] if values else ""
    if not secrets_equal(supplied, admin):
        return HttpResult(404, {"error": "Not found"})
    try:
        messages = await load_messages(db)
    except Exception:
        log.exception("D1 export failed")
        return HttpResult(500, {"error": "The export could not be read. See the worker logs for details."})
    return HttpResult(
        200,
        messages_to_csv(messages),
        "text/csv; charset=utf-8",
        {"Content-Disposition": 'attachment; filename="interviews.csv"'},
    )


async def dispatch(method, path, body, query, ctx):
    """Route one request. Always returns HttpResult; unexpected errors become a short JSON message."""
    try:
        return await _dispatch(method, path, body, query, ctx)
    except (ClientError, SessionError) as exc:
        return HttpResult(getattr(exc, "status", 400), {"error": str(exc)})
    except ProviderError as exc:
        # Full traceback stays in the worker logs. The client only sees `exc`'s message.
        log.exception("provider request failed")
        return HttpResult(exc.status, {"error": str(exc)})
    except Exception:
        log.exception("unhandled error")
        return HttpResult(500, {"error": "The interview service failed. See the worker logs for details."})


async def _dispatch(method, path, body, query, ctx):
    method = (method or "GET").upper()
    path = _normalise_path(path)

    if method == "GET" and path in ("/", "/healthcheck"):
        text = "Running!" if path == "/" else "ok"
        return HttpResult(200, text, "text/plain; charset=utf-8")

    if method == "GET" and path == "/interviews":
        return HttpResult(200, {"interviews": sorted(ctx.interviews)})

    if method == "GET" and path == "/export":
        return await run_export(query, ctx)

    if method == "GET" and path.startswith("/test/"):
        interview_id = unquote(path[len("/test/") :])
        if interview_id not in ctx.interviews:
            return HttpResult(404, {"error": f"Unknown interview '{interview_id}'."})
        return HttpResult(200, render_test_page(interview_id), "text/html; charset=utf-8")

    if method != "POST":
        raise ClientError("Method not allowed.", status=405)

    data = _parse_json_body(body)
    if path == "/":
        route = data.get("route")
        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            raise ClientError("payload must be an object.")
    elif path == "/next":
        route, payload = "next", data
    elif path == "/transcribe":
        route, payload = "transcribe", data
    else:
        raise ClientError("Not found.", status=404)

    if route == "next":
        return HttpResult(200, await run_next(payload, ctx))
    if route == "transcribe":
        return HttpResult(200, await run_transcribe(payload, ctx))
    raise ClientError(f"Unknown route: '{route}'.")
