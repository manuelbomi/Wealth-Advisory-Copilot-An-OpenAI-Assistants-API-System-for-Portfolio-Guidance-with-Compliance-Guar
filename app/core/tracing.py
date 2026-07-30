"""Lightweight tracing spans.

This is intentionally dependency-free (no OpenTelemetry SDK wired up) so the demo
stays runnable with zero external services. It emits structured log lines with
`span` + `duration_ms` fields that are trivially compatible with log-based tracing,
and the shape (name, attributes, start/end, duration) maps 1:1 onto an OTel span if a
reviewer wants to swap this for `opentelemetry-sdk` in a real deployment -- see the
"Observability" section of the README for how this would plug into
Prometheus/Grafana/Tempo in production.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger("tracing")


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    """Context manager that logs the start/end/duration of a named unit of work.

    Usage:
        with span("tool_call", tool_name="get_portfolio_holdings", client_id=cid):
            ...
    """
    start = time.perf_counter()
    logger.info("span_start", extra={"span": name, **attributes})
    try:
        yield
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.exception(
            "span_error", extra={"span": name, "duration_ms": duration_ms, **attributes}
        )
        raise
    else:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "span_end", extra={"span": name, "duration_ms": duration_ms, **attributes}
        )
