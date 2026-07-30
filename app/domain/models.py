"""Core domain models.

All data modeled here is synthetic and fictional -- see README.md. These models are
intentionally provider-agnostic: they know nothing about OpenAI, FastAPI, or SSE.
That separation is what lets `MockAssistantsClient` and the real OpenAI-backed client
share one set of tool contracts (app/tools) and one guardrail (app/guardrails)
without duplicating business logic.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator


class RiskProfile(str, enum.Enum):
    """Client suitability risk bucket -- drives the model portfolio target mix."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class AssetClass(str, enum.Enum):
    """Coarse asset-class buckets used for target vs. current allocation comparison."""

    EQUITIES = "equities"
    BONDS = "bonds"
    CASH = "cash"
    ALTERNATIVES = "alternatives"


class Holding(BaseModel):
    """A single position within a client's synthetic portfolio."""

    fund_id: str
    fund_name: str
    asset_class: AssetClass
    market_value_usd: float = Field(gt=0, description="Current market value in USD")


class ClientProfile(BaseModel):
    """A synthetic advisory client: identity, risk profile, and target allocation.

    `target_allocation` values are fractions (0.0-1.0) that must sum to ~1.0; this is
    enforced by `seed_data.py` at load time rather than here, since pydantic v2
    cross-field validation on a dict is awkward and the invariant only needs to hold
    for our fixed, small seed dataset.
    """

    client_id: str
    display_name: str
    risk_profile: RiskProfile
    target_allocation: dict[AssetClass, float]


class AllocationDrift(BaseModel):
    """Current vs. target allocation comparison for a single asset class."""

    asset_class: AssetClass
    current_weight: float = Field(description="Current allocation as a fraction of portfolio, e.g. 0.42")
    target_weight: float = Field(description="Target allocation as a fraction of portfolio, e.g. 0.40")
    drift: float = Field(description="current_weight - target_weight; positive = overweight")

    @property
    def is_within_tolerance(self) -> bool:
        """+/-5 percentage points is treated as "within tolerance" for this demo."""
        return abs(self.drift) <= 0.05


class ToolCallRecord(BaseModel):
    """Record of a single function-calling tool invocation, used for audit logging."""

    tool_name: str
    arguments: dict
    result_summary: str
    succeeded: bool = True


class GuardrailAction(str, enum.Enum):
    """Outcome of running the suitability guardrail over an outgoing assistant message."""

    PASS = "pass"
    ANNOTATED = "annotated"
    BLOCKED = "blocked"


class GuardrailDecision(BaseModel):
    """Result of the suitability guardrail evaluating a candidate assistant message."""

    action: GuardrailAction
    output_text: str
    matched_patterns: list[str] = Field(default_factory=list)
    reason: str = ""


class AuditLogEntry(BaseModel):
    """One immutable record of a completed assistant run, for compliance audit trail.

    Deliberately stores *summaries* of tool results, not full portfolio payloads --
    audit logs are often shipped to less-trusted downstream systems (SIEM, long-term
    archive) and should not become a second copy of sensitive client data.
    """

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str
    thread_id: str
    run_id: str
    client_id: str
    user_message: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    guardrail_action: GuardrailAction
    guardrail_reason: str = ""
    final_message_preview: str = Field(
        description="Truncated preview of the final assistant message (not full PII payloads)"
    )

    @field_validator("final_message_preview")
    @classmethod
    def _truncate(cls, v: str) -> str:
        return v[:280]


class ChatEventType(str, enum.Enum):
    """SSE event types streamed to the static chat client."""

    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    GUARDRAIL = "guardrail"
    TOKEN = "token"
    DONE = "done"
    ERROR = "error"


class ChatEvent(BaseModel):
    """A single Server-Sent Event payload."""

    type: ChatEventType
    data: dict


class ChatRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """A single turn stored on a client's persistent conversation thread."""

    role: ChatRole
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
