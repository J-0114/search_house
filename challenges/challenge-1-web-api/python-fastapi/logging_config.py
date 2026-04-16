"""
Structured JSON logging.

Usage anywhere in the codebase:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("something happened")        # requestId injected automatically

Correlation ID is stored in a ContextVar set by RequestIdMiddleware per request.
Non-request contexts (startup, CLI) receive "-" as the requestId.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Correlation-ID context variable
# ---------------------------------------------------------------------------

# Set by RequestIdMiddleware at the start of every HTTP / WebSocket request.
# Automatically included in every log record via JsonFormatter.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------

# Standard LogRecord attributes that should NOT be forwarded as extra fields.
_STANDARD_LOG_ATTRS = frozenset({
    "args", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "message", "module", "msecs", "msg",
    "name", "pathname", "process", "processName", "relativeCreated",
    "stack_info", "taskName", "thread", "threadName",
})


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()

        entry: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.message,
            "requestId": request_id_var.get(),
            "logger": record.name,
        }

        # Merge any fields passed via logger.info(..., extra={...})
        for key, val in record.__dict__.items():
            if key not in _STANDARD_LOG_ATTRS and not key.startswith("_"):
                entry[key] = val

        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(entry, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Setup helper — call once at application startup
# ---------------------------------------------------------------------------

def setup_logging(level: str = "INFO") -> None:
    """
    Configure the root logger to emit JSON to stdout.
    Replaces all existing handlers on the root logger.
    Silences uvicorn's plain-text access log (our middleware replaces it).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # uvicorn.access emits its own plain-text access log; our middleware
    # produces a structured equivalent, so suppress the duplicate.
    uv_access = logging.getLogger("uvicorn.access")
    uv_access.handlers.clear()
    uv_access.propagate = False

    # Let uvicorn's error/warning log flow through our JSON handler.
    logging.getLogger("uvicorn").propagate = True
    logging.getLogger("uvicorn.error").propagate = True
