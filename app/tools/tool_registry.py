"""Tool registry: OpenAI function-calling schemas + dispatch.

This is the single source of truth for "what tools exist". Both
`MockAssistantsClient` (offline) and `OpenAIAssistantsClient` (real API) import
`TOOL_SPECS` to configure the Assistant's `tools=[...]` and both call `dispatch_tool`
to actually execute a requested tool -- guaranteeing mock and real runs exercise
identical business logic, and only differ in *how* the model decides to call them.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.domain.exceptions import ClientNotFoundError
from app.tools.portfolio_tools import (
    calculate_allocation_drift,
    get_portfolio_holdings,
    get_risk_profile,
)

# JSON Schema tool descriptors in the shape the OpenAI Assistants API expects under
# `tools=[{"type": "function", "function": {...}}]`.
TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_holdings",
            "description": (
                "Get the client's current synthetic portfolio holdings "
                "(fund id, fund name, asset class, market value in USD)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "string",
                        "description": "Synthetic client identifier, e.g. 'NB-1001'.",
                    }
                },
                "required": ["client_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_risk_profile",
            "description": (
                "Get the client's suitability risk profile (conservative / moderate / "
                "aggressive) and target asset allocation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "string",
                        "description": "Synthetic client identifier, e.g. 'NB-1001'.",
                    }
                },
                "required": ["client_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_allocation_drift",
            "description": (
                "Compare the client's current portfolio allocation against their "
                "target allocation and return the drift per asset class."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {
                        "type": "string",
                        "description": "Synthetic client identifier, e.g. 'NB-1001'.",
                    }
                },
                "required": ["client_id"],
            },
        },
    },
]

# Maps tool name -> callable(**kwargs). All current tools take a single `client_id`
# kwarg, but this dispatcher does not assume that -- it forwards whatever the model
# supplied as JSON arguments.
_TOOL_IMPLS: dict[str, Callable[..., Any]] = {
    "get_portfolio_holdings": get_portfolio_holdings,
    "get_risk_profile": get_risk_profile,
    "calculate_allocation_drift": calculate_allocation_drift,
}


def known_tool_names() -> list[str]:
    return list(_TOOL_IMPLS.keys())


def dispatch_tool(tool_name: str, arguments: dict[str, Any]) -> tuple[Any, bool]:
    """Execute a tool by name and return (result, succeeded).

    Never raises: unknown tools and domain errors (e.g. unknown client_id) are
    converted into a structured error payload with succeeded=False so the calling
    run-loop can feed a meaningful error back to the model / audit log instead of
    the whole request blowing up on a single bad tool call.
    """
    impl = _TOOL_IMPLS.get(tool_name)
    if impl is None:
        return {"error": f"Unknown tool: {tool_name}"}, False
    try:
        result = impl(**arguments)
        return result, True
    except ClientNotFoundError as exc:
        return {"error": str(exc)}, False
    except TypeError as exc:
        # Malformed arguments from the model (missing/extra kwargs).
        return {"error": f"Invalid arguments for {tool_name}: {exc}"}, False
