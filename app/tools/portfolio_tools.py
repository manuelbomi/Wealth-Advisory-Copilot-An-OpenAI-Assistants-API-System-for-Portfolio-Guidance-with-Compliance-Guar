"""Portfolio function-calling tools.

Three tools, matching the job-relevant "agentic tool use" requirement:

    get_portfolio_holdings(client_id)      -> list of synthetic holdings
    get_risk_profile(client_id)             -> the client's suitability risk bucket
    calculate_allocation_drift(client_id)   -> current vs. target allocation, per
                                                asset class, computed from the
                                                in-memory synthetic portfolio

All three raise `ClientNotFoundError` for unknown client ids; the tool dispatcher
(`tool_registry.py`) catches that and turns it into a structured tool-error result
that gets fed back into the run, rather than crashing the whole request -- this
mirrors how a real Assistants integration must handle tool failures gracefully.
"""

from __future__ import annotations

from app.domain.exceptions import ClientNotFoundError
from app.domain.models import AllocationDrift, AssetClass, ClientProfile, Holding
from app.domain.seed_data import CLIENTS, HOLDINGS


def _get_client(client_id: str) -> ClientProfile:
    client = CLIENTS.get(client_id)
    if client is None:
        raise ClientNotFoundError(client_id)
    return client


def get_portfolio_holdings(client_id: str) -> list[dict]:
    """Return the synthetic current holdings for a client.

    Returns a list of plain dicts (JSON-serializable) rather than pydantic model
    instances because this is the boundary that gets serialized straight into a
    tool-call result sent back to the model.
    """
    if client_id not in CLIENTS:
        raise ClientNotFoundError(client_id)
    holdings: list[Holding] = HOLDINGS.get(client_id, [])
    return [h.model_dump(mode="json") for h in holdings]


def get_risk_profile(client_id: str) -> dict:
    """Return the client's suitability risk profile and target allocation."""
    client = _get_client(client_id)
    return {
        "client_id": client.client_id,
        "display_name": client.display_name,
        "risk_profile": client.risk_profile.value,
        "target_allocation": {k.value: v for k, v in client.target_allocation.items()},
    }


def calculate_allocation_drift(client_id: str) -> list[dict]:
    """Compute current vs. target allocation drift per asset class.

    Current weight for an asset class = sum(market_value for holdings in that
    class) / total portfolio market value. Drift = current_weight - target_weight
    (positive => overweight relative to target, negative => underweight).

    Asset classes present in the target allocation but with zero current holdings
    are still returned (current_weight=0.0) so a client can be alerted to a
    complete gap versus their target -- silently omitting them would hide the most
    actionable drift case.
    """
    client = _get_client(client_id)
    holdings = HOLDINGS.get(client_id, [])

    total_value = sum(h.market_value_usd for h in holdings)
    if total_value <= 0:
        # No holdings at all: every asset class is 100% underweight relative to target.
        current_by_class: dict[AssetClass, float] = {}
    else:
        current_by_class = {}
        for h in holdings:
            current_by_class[h.asset_class] = current_by_class.get(h.asset_class, 0.0) + h.market_value_usd
        current_by_class = {k: v / total_value for k, v in current_by_class.items()}

    all_classes = set(client.target_allocation.keys()) | set(current_by_class.keys())
    drifts = []
    for asset_class in sorted(all_classes, key=lambda c: c.value):
        target_weight = client.target_allocation.get(asset_class, 0.0)
        current_weight = current_by_class.get(asset_class, 0.0)
        drift = AllocationDrift(
            asset_class=asset_class,
            current_weight=round(current_weight, 4),
            target_weight=round(target_weight, 4),
            drift=round(current_weight - target_weight, 4),
        )
        drifts.append(drift.model_dump(mode="json"))
    return drifts
