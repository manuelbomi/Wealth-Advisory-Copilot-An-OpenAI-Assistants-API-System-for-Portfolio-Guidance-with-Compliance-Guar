"""Covers the MockAssistantsClient thread/run/tool-call lifecycle end to end.

This is the offline "happy path" required by the project spec: with no
OPENAI_API_KEY configured, the mock client must simulate the full lifecycle
(thread creation, tool-call dispatch, final message synthesis) deterministically.
"""

from __future__ import annotations

import pytest

from app.domain.models import ChatEventType
from app.infrastructure.mock_assistants_client import MockAssistantsClient


def test_ensure_thread_is_persistent_per_client(mock_client: MockAssistantsClient) -> None:
    thread_a1 = mock_client.ensure_thread("NB-1001")
    thread_a2 = mock_client.ensure_thread("NB-1001")
    thread_b = mock_client.ensure_thread("NB-1002")

    assert thread_a1 == thread_a2, "same client_id must reuse the same thread"
    assert thread_a1 != thread_b, "different clients must get different threads"
    assert thread_a1.startswith("thread_mock_")


@pytest.mark.asyncio
async def test_holdings_question_triggers_tool_call_and_returns_holdings(
    mock_client: MockAssistantsClient,
) -> None:
    thread_id = mock_client.ensure_thread("NB-1001")
    events = [e async for e in mock_client.run_turn("NB-1001", thread_id, "What are my current holdings?")]

    tool_calls = [e for e in events if e.type == ChatEventType.TOOL_CALL]
    tool_results = [e for e in events if e.type == ChatEventType.TOOL_RESULT]
    done_events = [e for e in events if e.type == ChatEventType.DONE]

    assert any(tc.data["tool_name"] == "get_portfolio_holdings" for tc in tool_calls)
    holdings_result = next(tr for tr in tool_results if tr.data["tool_name"] == "get_portfolio_holdings")
    assert holdings_result.data["succeeded"] is True
    fund_names = {h["fund_name"] for h in holdings_result.data["result"]}
    assert "Northbridge Global Equity Fund" in fund_names

    assert len(done_events) == 1
    final_text = done_events[0].data["final_text"]
    assert "Northbridge Global Equity Fund" in final_text
    assert done_events[0].data["thread_id"] == thread_id


@pytest.mark.asyncio
async def test_unknown_client_id_tool_call_fails_gracefully(mock_client: MockAssistantsClient) -> None:
    thread_id = mock_client.ensure_thread("NB-9999")
    events = [e async for e in mock_client.run_turn("NB-9999", thread_id, "show me my holdings")]

    tool_result = next(e for e in events if e.type == ChatEventType.TOOL_RESULT)
    assert tool_result.data["succeeded"] is False
    assert "Unknown client_id" in tool_result.data["result"]["error"]


@pytest.mark.asyncio
async def test_fund_question_triggers_file_search(mock_client: MockAssistantsClient) -> None:
    thread_id = mock_client.ensure_thread("NB-1001")
    events = [
        e
        async for e in mock_client.run_turn(
            "NB-1001", thread_id, "What is the objective of the Northbridge Balanced Growth Fund?"
        )
    ]
    tool_calls = [e for e in events if e.type == ChatEventType.TOOL_CALL]
    assert any(tc.data["tool_name"] == "file_search" for tc in tool_calls)
