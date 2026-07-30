"""Covers the function-calling tool logic, especially the allocation-drift
calculation, against the fixed synthetic seed portfolios in
app/domain/seed_data.py.

NB-1001 hand-computed expectation (total portfolio = $100,000):
    equities:      $65,000 / $100,000 = 0.65 current vs 0.55 target -> drift +0.10
    bonds:         $25,000 / $100,000 = 0.25 current vs 0.35 target -> drift -0.10
    cash:          $5,000  / $100,000 = 0.05 current vs 0.05 target -> drift  0.00
    alternatives:  $5,000  / $100,000 = 0.05 current vs 0.05 target -> drift  0.00

NB-1003 is seeded to land exactly on its target allocation (zero drift everywhere).
"""

from __future__ import annotations

import pytest

from app.domain.exceptions import ClientNotFoundError
from app.tools.portfolio_tools import (
    calculate_allocation_drift,
    get_portfolio_holdings,
    get_risk_profile,
)
from app.tools.tool_registry import dispatch_tool


def test_get_portfolio_holdings_returns_expected_holdings() -> None:
    holdings = get_portfolio_holdings("NB-1001")
    assert len(holdings) == 4
    fund_ids = {h["fund_id"] for h in holdings}
    assert fund_ids == {"NBG-EQ01", "NBG-BD01", "NBG-CASH", "NBG-ALT01"}
    equity_holding = next(h for h in holdings if h["fund_id"] == "NBG-EQ01")
    assert equity_holding["market_value_usd"] == 65_000
    assert equity_holding["asset_class"] == "equities"


def test_get_portfolio_holdings_unknown_client_raises() -> None:
    with pytest.raises(ClientNotFoundError):
        get_portfolio_holdings("NOT-A-REAL-CLIENT")


def test_get_risk_profile() -> None:
    profile = get_risk_profile("NB-1002")
    assert profile["risk_profile"] == "aggressive"
    assert profile["target_allocation"]["equities"] == pytest.approx(0.75)


def test_calculate_allocation_drift_matches_hand_computed_values() -> None:
    drift = calculate_allocation_drift("NB-1001")
    drift_by_class = {d["asset_class"]: d for d in drift}

    assert drift_by_class["equities"]["current_weight"] == pytest.approx(0.65)
    assert drift_by_class["equities"]["target_weight"] == pytest.approx(0.55)
    assert drift_by_class["equities"]["drift"] == pytest.approx(0.10)

    assert drift_by_class["bonds"]["current_weight"] == pytest.approx(0.25)
    assert drift_by_class["bonds"]["target_weight"] == pytest.approx(0.35)
    assert drift_by_class["bonds"]["drift"] == pytest.approx(-0.10)

    assert drift_by_class["cash"]["drift"] == pytest.approx(0.0)
    assert drift_by_class["alternatives"]["drift"] == pytest.approx(0.0)


def test_calculate_allocation_drift_zero_for_on_target_client() -> None:
    drift = calculate_allocation_drift("NB-1003")
    for d in drift:
        assert d["drift"] == pytest.approx(0.0, abs=1e-9)


def test_dispatch_tool_unknown_tool_name_does_not_raise() -> None:
    result, ok = dispatch_tool("not_a_real_tool", {})
    assert ok is False
    assert "Unknown tool" in result["error"]


def test_dispatch_tool_bad_arguments_does_not_raise() -> None:
    result, ok = dispatch_tool("get_portfolio_holdings", {"unexpected_kwarg": "x"})
    assert ok is False
    assert "Invalid arguments" in result["error"]
