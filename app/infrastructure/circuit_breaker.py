"""Minimal in-process circuit breaker for outbound OpenAI API calls.

Paired with `tenacity` retries in `openai_assistants_client.py`: retries handle
*transient* failures on a single call, the circuit breaker handles *sustained*
failure (e.g. an OpenAI outage) by short-circuiting further attempts for a cooldown
window instead of letting every incoming chat request hang on a doomed retry loop.

Deliberately hand-rolled rather than pulling in a dependency like `pybreaker` --
the state machine is ~30 lines and keeping it in-repo makes the behavior obvious to
a reviewer, which matters more here than saving a few lines.
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum

logger = logging.getLogger("circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "closed"       # normal operation
    OPEN = "open"            # failing fast, not calling downstream
    HALF_OPEN = "half_open"  # cooldown elapsed, allowing one trial call


class CircuitOpenError(RuntimeError):
    """Raised instead of attempting a call while the breaker is OPEN."""


class CircuitBreaker:
    """Simple failure-count-threshold circuit breaker.

    - Starts CLOSED.
    - After `failure_threshold` consecutive failures, trips to OPEN.
    - After `reset_seconds`, moves to HALF_OPEN and allows exactly one trial call.
    - A successful trial call closes the circuit; a failed one re-opens it and
      resets the cooldown timer.
    """

    def __init__(self, failure_threshold: int = 5, reset_seconds: float = 30.0) -> None:
        self._failure_threshold = failure_threshold
        self._reset_seconds = reset_seconds
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    def _maybe_transition_to_half_open(self) -> None:
        if (
            self._state == CircuitState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self._reset_seconds
        ):
            self._state = CircuitState.HALF_OPEN
            logger.info("circuit_half_open")

    def before_call(self) -> None:
        """Call before attempting the guarded operation. Raises CircuitOpenError
        if calls should currently be short-circuited."""
        with self._lock:
            self._maybe_transition_to_half_open()
            if self._state == CircuitState.OPEN:
                raise CircuitOpenError(
                    "Circuit breaker is open -- OpenAI calls are being short-circuited "
                    "after repeated failures. Will retry after cooldown."
                )

    def record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            if self._state != CircuitState.CLOSED:
                logger.info("circuit_closed_after_success")
            self._state = CircuitState.CLOSED
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._state == CircuitState.HALF_OPEN or (
                self._consecutive_failures >= self._failure_threshold
            ):
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    "circuit_open", extra={"consecutive_failures": self._consecutive_failures}
                )
