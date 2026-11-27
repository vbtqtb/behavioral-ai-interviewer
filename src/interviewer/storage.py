"""Optional D1 backup. Qualtrics embedded data is the store that matters.

If the Worker has no DB binding these functions are not called. Table creation
is lazy so a fresh database needs no migration step.
"""

import csv
import io
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    session_json TEXT NOT NULL,
    transcript TEXT NOT NULL
)
"""

UPSERT_SESSION = """
INSERT INTO sessions (session_id, interview_id, updated_at, session_json, transcript)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(session_id) DO UPDATE SET
    interview_id = excluded.interview_id,
    updated_at = excluded.updated_at,
    session_json = excluded.session_json,
    transcript = excluded.transcript
"""


def to_python(obj):
    """Turn a Workers/JS value into plain Python, leaving Python values alone."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(key): to_python(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_python(value) for value in obj]
    convert = getattr(obj, "to_py", None)
    if callable(convert):
        return to_python(convert())
    keys = getattr(obj, "keys", None)
    if callable(keys):
        try:
            return {str(key): to_python(obj[key]) for key in list(keys())}
        except Exception:
            pass
    try:
        return [to_python(obj[index]) for index in range(len(obj))]
    except Exception:
        return str(obj)


async def ensure_table(db):
    """Create the sessions table if this database does not have it yet."""
    await db.prepare(CREATE_SESSIONS).run()


async def save_session(db, session_id, interview_id, session, transcript):
    """Insert or replace one interview. Failures are logged by the caller."""
    await ensure_table(db)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    await db.prepare(UPSERT_SESSION).bind(
        session_id,
        interview_id,
        updated,
        json.dumps(session, ensure_ascii=False),
        transcript or "",
    ).run()


async def load_messages(db):
    """Return every stored turn, one dict per message, ordered by session id."""
    await ensure_table(db)
    result = await db.prepare(
        "SELECT session_id, session_json FROM sessions ORDER BY session_id"
    ).run()
    data = to_python(result)
    rows = []
    if isinstance(data, dict):
        rows = data.get("results") or []
    messages = []
    for row in rows:
        row = to_python(row)
        if not isinstance(row, dict):
            continue
        raw = row.get("session_json")
        if not raw:
            continue
        try:
            session = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Skipping session %s: session_json is not valid JSON", row.get("session_id"))
            continue
        if isinstance(session, list):
            messages.extend(session)
    return messages


def messages_to_csv(messages):
    """One CSV row per message, same shape as the old retrieve.py export."""
    preferred = [
        "session_id",
        "order",
        "time",
        "type",
        "content",
        "topic_idx",
        "question_idx",
        "finish_idx",
        "flagged_messages",
        "terminated",
        "summary",
    ]
    keys = []
    seen = set()
    for key in preferred:
        if any(isinstance(message, dict) and key in message for message in messages):
            keys.append(key)
            seen.add(key)
    for message in messages:
        if not isinstance(message, dict):
            continue
        for key in message:
            if key not in seen:
                keys.append(key)
                seen.add(key)
    if not keys:
        keys = ["session_id"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=keys, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for message in messages:
        if not isinstance(message, dict):
            continue
        flat = {}
        for key in keys:
            value = message.get(key, "")
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            elif value is None:
                value = ""
            elif isinstance(value, bool):
                value = "true" if value else "false"
            flat[key] = value
        writer.writerow(flat)
    return buffer.getvalue()
