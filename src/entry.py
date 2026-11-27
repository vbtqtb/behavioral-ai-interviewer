"""Cloudflare Worker entrypoint.

Request handling lives in interviewer.service so the same code runs under
plain CPython tests. This file only adapts the Workers request and response.
"""

import logging
from urllib.parse import parse_qs, urlparse

from workers import Response, WorkerEntrypoint

from interviewer.errors import env_text
from interviewer.service import CORS_HEADERS, Context, HttpResult, dispatch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)


def _worker_response(result: HttpResult):
    headers = dict(CORS_HEADERS)
    headers.update(result.headers)
    if result.content_type.startswith("application/json"):
        return Response.json(result.body, status=result.status, headers=headers)
    headers["Content-Type"] = result.content_type
    text = result.body if isinstance(result.body, str) else ""
    return Response(text, status=result.status, headers=headers)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        if request.method == "OPTIONS":
            return Response("", status=204, headers=dict(CORS_HEADERS))
        try:
            parsed = urlparse(request.url)
            body = ""
            if request.method.upper() in ("POST", "PUT", "PATCH"):
                body = await request.text()
            ctx = Context(
                env=self.env,
                db=getattr(self.env, "DB", None),
                admin_password=env_text(self.env, "ADMIN_PASSWORD"),
            )
            result = await dispatch(
                request.method,
                parsed.path,
                body,
                parse_qs(parsed.query),
                ctx,
            )
        except Exception:
            log.exception("request failed before dispatch")
            result = HttpResult(
                500,
                {"error": "The interview service failed. See the worker logs for details."},
            )
        return _worker_response(result)
