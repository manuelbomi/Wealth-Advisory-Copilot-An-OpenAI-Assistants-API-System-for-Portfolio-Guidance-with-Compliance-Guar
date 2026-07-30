"""Chat API: client listing + the streaming (SSE) chat endpoint.

The streaming endpoint is intentionally POST (not a plain EventSource GET) because
it needs a JSON body -- the static frontend (static/app.js) reads the response body
as a stream and parses `event:`/`data:` lines itself, which is a well-established
pattern for POST-initiated SSE where the browser's native EventSource (GET-only)
doesn't apply.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_advisory_service
from app.api.schemas import ChatRequest, ClientSummary
from app.domain.seed_data import CLIENTS
from app.service.advisory_service import AdvisoryService

logger = logging.getLogger("routes_chat")

router = APIRouter(prefix="/api", tags=["chat"])


@router.get("/clients", response_model=list[ClientSummary])
def list_clients() -> list[ClientSummary]:
    """List the synthetic Northbridge demo clients, for the frontend's picker."""
    return [
        ClientSummary(client_id=c.client_id, display_name=c.display_name, risk_profile=c.risk_profile)
        for c in CLIENTS.values()
    ]


@router.post("/chat/{client_id}/stream")
async def stream_chat(
    client_id: str,
    body: ChatRequest,
    advisory_service: AdvisoryService = Depends(get_advisory_service),
) -> StreamingResponse:
    if client_id not in CLIENTS:
        # Boundary validation: fail fast with a clear 404 rather than letting an
        # unknown client_id silently propagate into tool calls.
        raise HTTPException(status_code=404, detail=f"Unknown client_id: {client_id}")

    async def event_source():
        async for event in advisory_service.handle_chat_turn(client_id, body.message):
            payload = json.dumps(event.data, default=str)
            yield f"event: {event.type.value}\ndata: {payload}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering so chunks flush immediately
        },
    )
