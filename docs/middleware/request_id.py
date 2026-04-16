"""
Request-ID (correlation ID) ASGI middleware.

For every HTTP request and WebSocket connection:
  1. Reads X-Request-ID from the incoming headers (allows callers to propagate
     an existing trace ID).  Falls back to a freshly generated UUID v4.
  2. Stores the ID in `request_id_var` so every log call made during the
     request automatically includes it.
  3. Appends X-Request-ID to the response headers so clients can correlate
     logs without scraping the log stream.
  4. Emits two structured log lines:
       • "request started"  — method, path, client IP
       • "request finished" — method, path, status code, duration_ms
"""

import logging
import time
import uuid
from typing import Callable

from logging_config import request_id_var

logger = logging.getLogger(__name__)


class RequestIdMiddleware:
    """Pure ASGI middleware — no Starlette BaseHTTPMiddleware wrapper,
    so ContextVar propagation into route handlers is reliable."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # ── Resolve request ID ────────────────────────────────────────────
        raw_headers: dict[bytes, bytes] = {
            k.lower(): v for k, v in scope.get("headers", [])
        }
        req_id = (
            raw_headers.get(b"x-request-id", b"").decode()
            or str(uuid.uuid4())
        )

        # Bind to ContextVar for this execution context
        token = request_id_var.set(req_id)

        # ── Log request start ─────────────────────────────────────────────
        method = scope.get("method", "WS")
        path = scope.get("path", "")
        client = scope.get("client")
        client_ip = client[0] if client else "-"
        t0 = time.perf_counter()

        logger.info(
            "request started",
            extra={"method": method, "path": path, "clientIp": client_ip},
        )

        # ── Send wrapper — capture status & inject response header ────────
        status_code: int = 0

        async def send_wrapper(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers: list = list(message.get("headers", []))
                headers.append((b"x-request-id", req_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        # ── Run the actual app ────────────────────────────────────────────
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            logger.info(
                "request finished",
                extra={
                    "method": method,
                    "path": path,
                    "status": status_code,
                    "durationMs": duration_ms,
                },
            )
            request_id_var.reset(token)
