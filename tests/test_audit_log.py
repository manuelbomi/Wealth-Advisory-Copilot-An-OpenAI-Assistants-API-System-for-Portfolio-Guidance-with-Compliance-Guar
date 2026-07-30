"""Covers the compliance audit trail: every completed assistant run must produce
exactly one audit log entry recording the client, tool calls, and guardrail
action taken.
"""

from __future__ import annotations

import pytest

from app.domain.models import ChatEventType, GuardrailAction
from app.infrastructure.audit_log import AuditLogWriter
from app.service.advisory_service import AdvisoryService


@pytest.mark.asyncio
async def test_handle_chat_turn_writes_one_audit_entry(
    advisory_service: AdvisoryService, audit_log_writer: AuditLogWriter
) -> None:
    events = [e async for e in advisory_service.handle_chat_turn("NB-1001", "What are my current holdings?")]

    # Sanity: the turn actually ran a tool and completed.
    assert any(e.type == ChatEventType.TOOL_CALL for e in events)
    assert any(e.type == ChatEventType.DONE for e in events)

    entries = audit_log_writer.read_all()
    assert len(entries) == 1

    entry = entries[0]
    assert entry.client_id == "NB-1001"
    assert entry.user_message == "What are my current holdings?"
    assert len(entry.tool_calls) >= 1
    assert entry.tool_calls[0].tool_name == "get_portfolio_holdings"
    assert entry.guardrail_action in {GuardrailAction.PASS, GuardrailAction.ANNOTATED, GuardrailAction.BLOCKED}
    assert entry.run_id  # non-empty
    assert entry.thread_id  # non-empty


@pytest.mark.asyncio
async def test_guardrail_block_is_reflected_in_audit_log(
    advisory_service: AdvisoryService, audit_log_writer: AuditLogWriter
) -> None:
    # This message baits the (deliberately naive) mock model into an unsafe
    # "guaranteed return" claim, which the guardrail must then block -- and the
    # audit log must faithfully record that a BLOCKED action was taken.
    events = [
        e
        async for e in advisory_service.handle_chat_turn(
            "NB-1001", "Can you guarantee returns on this fund?"
        )
    ]
    guardrail_events = [e for e in events if e.type == ChatEventType.GUARDRAIL]
    assert guardrail_events[0].data["action"] == "blocked"

    entries = audit_log_writer.read_all()
    assert entries[-1].guardrail_action == GuardrailAction.BLOCKED


@pytest.mark.asyncio
async def test_two_turns_append_two_audit_entries(
    advisory_service: AdvisoryService, audit_log_writer: AuditLogWriter
) -> None:
    async for _ in advisory_service.handle_chat_turn("NB-1002", "What is my risk profile?"):
        pass
    async for _ in advisory_service.handle_chat_turn("NB-1003", "Show me allocation drift"):
        pass

    entries = audit_log_writer.read_all()
    assert len(entries) == 2
    assert {e.client_id for e in entries} == {"NB-1002", "NB-1003"}
