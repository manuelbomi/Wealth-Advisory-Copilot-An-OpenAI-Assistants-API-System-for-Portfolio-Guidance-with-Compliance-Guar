"""MockAssistantsClient: a deterministic, fully offline simulation of the OpenAI
Assistants API thread/run/tool-call lifecycle.

This is what makes the whole project clonable and runnable with zero paid API
keys: when `OPENAI_API_KEY` is not set, `client_factory.get_assistants_client`
returns an instance of this class instead of `OpenAIAssistantsClient`, and the
rest of the application (service layer, API routes, guardrail, audit log) cannot
tell the difference -- it only sees the `AssistantsClient` Protocol.

Simulated lifecycle, mirroring the real API's shape:

    1. ensure_thread(client_id)      -- "POST /threads" (idempotent per client)
    2. add user message to thread     -- "POST /threads/{id}/messages"
    3. create a run                    -- "POST /threads/{id}/runs"
    4. inspect the user message with keyword heuristics standing in for the
       model's own tool-selection reasoning, and "call" zero or more tools --
       "run.status == requires_action" -> dispatch_tool(...) -> submit outputs
    5. synthesize a final assistant message from the tool outputs -- "run.status
       == completed" -> retrieve last message
    6. yield ChatEvents the whole way so the API layer can stream progress over SSE

Keyword-matching here is intentionally simple and inspectable (not a toy LLM) --
the goal is a deterministic stand-in for "the model decided to call tool X", not a
demonstration of NLU.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator

from app.domain.models import ChatEvent, ChatEventType
from app.infrastructure.fund_factsheet_store import FundFactsheetStore
from app.tools.tool_registry import dispatch_tool


class MockAssistantsClient:
    """Offline stand-in for the real OpenAI Assistants API client."""

    def __init__(self, factsheet_store: FundFactsheetStore) -> None:
        self._factsheet_store = factsheet_store
        # client_id -> thread_id. A plain dict is enough for this single-process
        # demo; a real deployment would persist this mapping (e.g. in a database)
        # so threads survive process restarts.
        self._threads: dict[str, str] = {}

    def ensure_thread(self, client_id: str) -> str:
        thread_id = self._threads.get(client_id)
        if thread_id is None:
            thread_id = f"thread_mock_{uuid.uuid4().hex[:16]}"
            self._threads[client_id] = thread_id
        return thread_id

    async def run_turn(self, client_id: str, thread_id: str, user_message: str) -> AsyncIterator[ChatEvent]:
        run_id = f"run_mock_{uuid.uuid4().hex[:16]}"
        lowered = user_message.lower()

        response_sections: list[str] = []

        # --- Tool-selection heuristics (stand-in for the model's own reasoning) ---
        if _wants_holdings(lowered):
            args = {"client_id": client_id}
            yield ChatEvent(type=ChatEventType.TOOL_CALL, data={"tool_name": "get_portfolio_holdings", "arguments": args, "run_id": run_id})
            result, ok = dispatch_tool("get_portfolio_holdings", args)
            yield ChatEvent(type=ChatEventType.TOOL_RESULT, data={"tool_name": "get_portfolio_holdings", "result": result, "succeeded": ok, "run_id": run_id})
            response_sections.append(_render_holdings(result) if ok else f"I couldn't retrieve holdings: {result.get('error')}")

        if _wants_risk_profile(lowered):
            args = {"client_id": client_id}
            yield ChatEvent(type=ChatEventType.TOOL_CALL, data={"tool_name": "get_risk_profile", "arguments": args, "run_id": run_id})
            result, ok = dispatch_tool("get_risk_profile", args)
            yield ChatEvent(type=ChatEventType.TOOL_RESULT, data={"tool_name": "get_risk_profile", "result": result, "succeeded": ok, "run_id": run_id})
            response_sections.append(_render_risk_profile(result) if ok else f"I couldn't retrieve the risk profile: {result.get('error')}")

        if _wants_drift(lowered):
            args = {"client_id": client_id}
            yield ChatEvent(type=ChatEventType.TOOL_CALL, data={"tool_name": "calculate_allocation_drift", "arguments": args, "run_id": run_id})
            result, ok = dispatch_tool("calculate_allocation_drift", args)
            yield ChatEvent(type=ChatEventType.TOOL_RESULT, data={"tool_name": "calculate_allocation_drift", "result": result, "succeeded": ok, "run_id": run_id})
            response_sections.append(_render_drift(result) if ok else f"I couldn't calculate drift: {result.get('error')}")

        if _wants_file_search(lowered):
            yield ChatEvent(type=ChatEventType.TOOL_CALL, data={"tool_name": "file_search", "arguments": {"query": user_message}, "run_id": run_id})
            matches = self._factsheet_store.search(user_message, top_k=2)
            result = [m.__dict__ for m in matches]
            yield ChatEvent(type=ChatEventType.TOOL_RESULT, data={"tool_name": "file_search", "result": result, "succeeded": True, "run_id": run_id})
            response_sections.append(_render_file_search(matches))

        if not response_sections:
            response_sections.append(_render_fallback(user_message))

        # Adversarial demo hook: if the user is baiting the assistant into an
        # unsafe claim ("guarantee", "risk free", "should i buy"), the mock model
        # deliberately produces the *unsafe* phrasing here so the guardrail
        # middleware (applied downstream in the service layer, not here) has
        # something real to catch -- this exercises the full defense-in-depth
        # path end to end via the API, not just via direct unit tests.
        response_sections.append(_maybe_unsafe_addendum(lowered))

        final_text = "\n\n".join(s for s in response_sections if s)

        yield ChatEvent(
            type=ChatEventType.DONE,
            data={"run_id": run_id, "thread_id": thread_id, "final_text": final_text},
        )


# --- keyword heuristics -----------------------------------------------------------

def _wants_holdings(text: str) -> bool:
    return any(kw in text for kw in ("holding", "portfolio", "position", "what do i own", "what am i invested"))


def _wants_risk_profile(text: str) -> bool:
    return any(kw in text for kw in ("risk profile", "risk tolerance", "how risky", "my risk"))


def _wants_drift(text: str) -> bool:
    return any(kw in text for kw in ("drift", "rebalance", "out of balance", "allocation", "target mix", "on target"))


def _wants_file_search(text: str) -> bool:
    return any(
        kw in text
        for kw in ("fund", "fact sheet", "factsheet", "prospectus", "objective", "expense ratio", "balanced growth", "global equity", "sustainable", "short duration")
    )


_GUARANTEE_BAIT = re.compile(r"\bguarante|risk[- ]free|can'?t lose\b", re.IGNORECASE)
_BUY_BAIT = re.compile(r"\bshould i buy\b|\bwhat should i buy\b", re.IGNORECASE)


def _maybe_unsafe_addendum(lowered_text: str) -> str:
    """Deliberately-naive response text used only to demo the guardrail catching
    unsafe language end-to-end; see module docstring."""
    if _GUARANTEE_BAIT.search(lowered_text):
        return "To directly answer: yes, this fund offers a guaranteed return with no downside risk."
    if _BUY_BAIT.search(lowered_text):
        return "Based on that, you should buy the Northbridge Balanced Growth Fund right away."
    return ""


# --- response rendering ------------------------------------------------------------

def _render_holdings(holdings: list[dict]) -> str:
    if not holdings:
        return "You currently have no recorded holdings."
    lines = [f"- {h['fund_name']} ({h['asset_class']}): ${h['market_value_usd']:,.2f}" for h in holdings]
    return "Here are your current synthetic holdings:\n" + "\n".join(lines)


def _render_risk_profile(profile: dict) -> str:
    target = ", ".join(f"{k}: {v:.0%}" for k, v in profile["target_allocation"].items())
    return (
        f"Your risk profile is **{profile['risk_profile']}**. "
        f"Your target allocation is {target}."
    )


def _render_drift(drifts: list[dict]) -> str:
    lines = []
    for d in drifts:
        flag = "within tolerance" if abs(d["drift"]) <= 0.05 else "OUTSIDE tolerance"
        lines.append(
            f"- {d['asset_class']}: current {d['current_weight']:.1%} vs target {d['target_weight']:.1%} "
            f"(drift {d['drift']:+.1%}, {flag})"
        )
    return "Allocation drift versus your target:\n" + "\n".join(lines)


def _render_file_search(matches: list) -> str:
    if not matches:
        return "I couldn't find a matching fund fact sheet for that query."
    lines = []
    for m in matches:
        lines.append(f"From {m.fund_name} ({m.source_file}): \"{m.snippet}\"")
    return "Relevant fund fact sheet excerpts:\n" + "\n".join(lines)


def _render_fallback(user_message: str) -> str:
    return (
        "I can help with your portfolio holdings, risk profile, allocation drift "
        "versus your target mix, and Northbridge fund fact sheets. Could you "
        "clarify what you'd like to know?"
    )
