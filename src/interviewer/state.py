"""HMAC signatures for the interview session the browser sends back each turn.

The worker stores nothing. The signature is what stops a respondent from editing
their own history (topic index, flags, the stored DAG) between requests.
"""

import hashlib
import hmac
import json


class SessionError(Exception):
    """The browser sent a session that was missing or no longer matches its signature."""

    status = 400


def derived_key(api_key):
    """Key used when SESSION_SECRET is not set. Tied to whichever provider key is active."""
    return hashlib.sha256(b"ai-interviewer-session:" + api_key.encode("utf-8")).digest()


def make_signing_key(session_secret, api_key):
    """SESSION_SECRET if it is set, otherwise a digest of the active provider API key."""
    if session_secret:
        return session_secret.encode("utf-8")
    if not api_key:
        raise SessionError("Set SESSION_SECRET or the API key for the selected provider before starting an interview.")
    return derived_key(api_key)


def canonical_session(session):
    """Stable bytes for signing. Key order in the browser's JSON does not matter."""
    return json.dumps(session, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sign_session(session, key):
    """Return the hex HMAC-SHA256 of the session."""
    return hmac.new(key, canonical_session(session), hashlib.sha256).hexdigest()


def verify_session(session, signature, key):
    """Raise SessionError when the signature is missing or does not match."""
    if not isinstance(signature, str) or not signature:
        raise SessionError("Session signature is missing.")
    expected = sign_session(session, key)
    try:
        matches = hmac.compare_digest(expected, signature)
    except Exception:
        matches = False
    if not matches:
        raise SessionError("Session signature is invalid. The session was modified or signed with a different key.")


def secrets_equal(left, right):
    """Constant-time string compare. Different lengths are simply not equal."""
    if left is None or right is None:
        return False
    try:
        return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
    except Exception:
        return False
