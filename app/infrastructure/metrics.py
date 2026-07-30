"""Prometheus metrics.

Exposes a `/metrics` endpoint (wired in app.api.routes_health) in the standard
Prometheus text exposition format. See the README "Observability" section for how
these would be scraped by Prometheus and visualized in Grafana, and how per-client
token/cost tracking would extend `record_run`.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

ASSISTANT_RUNS_TOTAL = Counter(
    "assistant_runs_total", "Total number of assistant chat runs processed", ["client_id"]
)
TOOL_CALLS_TOTAL = Counter(
    "tool_calls_total", "Total number of function-calling tool invocations", ["tool_name", "succeeded"]
)
GUARDRAIL_ACTIONS_TOTAL = Counter(
    "guardrail_actions_total", "Total guardrail decisions taken on outgoing messages", ["action"]
)
RUN_DURATION_SECONDS = Histogram(
    "assistant_run_duration_seconds", "Wall-clock duration of a full assistant run"
)


def render_latest() -> tuple[bytes, str]:
    """Return (body, content_type) for the /metrics endpoint."""
    return generate_latest(), CONTENT_TYPE_LATEST
