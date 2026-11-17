"""Structured, request-id aware logging (JSON or human-readable text)."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

#: The id of the request being handled (set by ``RequestContextMiddleware``).
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

TEXT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(request_id)s | %(message)s"

# Attributes every LogRecord has; anything else was passed via `extra=` and goes into the JSON.
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
    "request_id",
}

_factory_installed = False


def _install_record_factory() -> None:
    """Give EVERY log record (ours and third-party) a ``request_id`` attribute."""
    global _factory_installed
    if _factory_installed:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:  # noqa: ANN401
        record = previous(*args, **kwargs)
        record.request_id = request_id_var.get() or "-"
        return record

    logging.setLogRecordFactory(factory)
    _factory_installed = True


class JsonFormatter(logging.Formatter):
    """One JSON object per line: ts, level, logger, message, request_id, extras, exc_info."""

    def format(self, record: logging.LogRecord) -> str:
        request_id = getattr(record, "request_id", "-")
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": None if request_id == "-" else request_id,
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_logging(*, level: str, json_logs: bool) -> None:
    """Configure the root logger (stdout) and quiet uvicorn's duplicate access log."""
    _install_record_factory()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_logs else logging.Formatter(TEXT_FORMAT))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)

    # uvicorn: route its error log through our handler; our own access log replaces its one.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
