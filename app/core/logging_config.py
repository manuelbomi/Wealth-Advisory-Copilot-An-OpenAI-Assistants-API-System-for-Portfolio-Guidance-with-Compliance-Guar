"""Structured (JSON) logging configuration.

Financial-services production systems need logs that are machine-parseable (for
SIEM / log aggregation ingestion) and that never leak secrets or raw PII. This module
configures the root logger to emit single-line JSON records and provides a
`correlation_id` contextvar so every log line inside a single chat "run" can be
stitched back together in a log viewer, without threading an id through every
function signature by hand.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# Context-local correlation id (set to the Assistants "run_id" for the duration of a
# single chat turn). Using a contextvar means concurrent requests in the same async
# process never leak each other's correlation ids.
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="-"
)

# Field names that must never appear in log output even if accidentally passed in
# `extra=...`. Defense in depth on top of "just don't log secrets".
_REDACT_KEYS = {"openai_api_key", "api_key", "authorization", "password", "secret"}


class JsonLogFormatter(logging.Formatter):
    """Renders each LogRecord as a single JSON line.

    WHY JSON and not plain text: structured logs can be filtered/aggregated by
    `client_id`, `run_id`, `tool_name`, etc. in any log platform without regex
    scraping, which matters once this runs in a real observability stack.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get(),
        }

        # Merge any structured extras the caller passed via logger.info(..., extra={...})
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOGRECORD_KEYS or key in _REDACT_KEYS:
                continue
            if key.lower() in _REDACT_KEYS:
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


# Attribute names that exist on every stdlib LogRecord -- used to distinguish
# "extra" fields the application code deliberately attached.
_STANDARD_LOGRECORD_KEYS = set(
    logging.LogRecord(
        name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
    ).__dict__.keys()
)


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Idempotently configure the root logger.

    Called once at process startup (see app.main). Safe to call multiple times
    (e.g. once from tests, once from the app) because it clears existing handlers
    before attaching a fresh one.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()

    handler = logging.StreamHandler(stream=sys.stdout)
    if json_output:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    root.addHandler(handler)

    # Quiet noisy third-party loggers down to WARNING so audit-relevant lines aren't
    # drowned out in local dev.
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
