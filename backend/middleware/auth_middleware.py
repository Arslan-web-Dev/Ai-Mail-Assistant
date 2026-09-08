"""
Note on approach: authentication is enforced per-route via the
`get_current_user` FastAPI dependency (app/dependencies.py) rather than a
blanket ASGI middleware. This is intentional — it keeps public routes
(`/health`, `/api/v1/gmail/callback`) explicit and opt-in, and it lets
FastAPI generate correct OpenAPI docs (401 responses only show up on routes
that actually require auth) — a global middleware can't express "some
routes are public" as cleanly and is easy to misconfigure.

This module holds cross-cutting request middleware instead (e.g. logging).
"""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("ai_mail_assistant.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s %s %.1fms [%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
