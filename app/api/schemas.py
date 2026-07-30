"""API request/response models.

Every inbound request is validated through one of these pydantic models before it
reaches the service layer -- e.g. `ChatRequest` bounds message length, which is
both an input-validation and a basic cost/abuse control on the (simulated) LLM
call.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models import RiskProfile


class ChatRequest(BaseModel):
    """Body of POST /api/chat/{client_id}/stream."""

    message: str = Field(min_length=1, max_length=4000, description="The user's chat message")


class ClientSummary(BaseModel):
    """Lightweight client descriptor used to populate the frontend's client picker."""

    client_id: str
    display_name: str
    risk_profile: RiskProfile


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    mock_mode: bool
    fund_factsheets_loaded: int
