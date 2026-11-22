"""Request ID untuk tracing (PRD §9.11)."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_request_id: ContextVar[str] = ContextVar("request_id", default="")


def current_request_id() -> str:
    return _request_id.get() or ""


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        incoming = request.headers.get("X-Request-Id", "")
        rid = incoming if 0 < len(incoming) <= 64 and incoming.replace("-", "").isalnum() else str(uuid.uuid4())
        token = _request_id.set(rid)
        try:
            response = await call_next(request)
        finally:
            _request_id.reset(token)
        response.headers["X-Request-Id"] = rid
        return response
