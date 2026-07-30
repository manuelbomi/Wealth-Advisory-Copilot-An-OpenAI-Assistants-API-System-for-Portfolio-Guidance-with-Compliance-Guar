"""In-memory synthetic seed data.

Everything in this module is fictional demo data for "Northbridge Financial Group",
an invented bank brand used solely to make the demo concrete. No real client,
account, or holding data is used anywhere in this repository.

Three synthetic clients are seeded with deliberately different drift profiles so the
`calculate_allocation_drift` tool (and its unit test) has interesting, hand-verifiable
fixtures:

  * NB-1001 (moderate)     -> meaningfully overweight equities / underweight bonds
  * NB-1002 (aggressive)   -> mildly overweight bonds/cash, within tolerance
  * NB-1003 (conservative) -> exactly on target (zero drift)
"""

from __future__ import annotations

from app.domain.models import AssetClass, ClientProfile, Holding, RiskProfile

CLIENTS: dict[str, ClientProfile] = {
    "NB-1001": ClientProfile(
        client_id="NB-1001",
        display_name="Jane Prospect",
        risk_profile=RiskProfile.MODERATE,
        target_allocation={
            AssetClass.EQUITIES: 0.55,
            AssetClass.BONDS: 0.35,
            AssetClass.CASH: 0.05,
            AssetClass.ALTERNATIVES: 0.05,
        },
    ),
    "NB-1002": ClientProfile(
        client_id="NB-1002",
        display_name="Alex Founder",
        risk_profile=RiskProfile.AGGRESSIVE,
        target_allocation={
            AssetClass.EQUITIES: 0.75,
            AssetClass.BONDS: 0.10,
            AssetClass.CASH: 0.05,
            AssetClass.ALTERNATIVES: 0.10,
        },
    ),
    "NB-1003": ClientProfile(
        client_id="NB-1003",
        display_name="Morgan Retiree",
        risk_profile=RiskProfile.CONSERVATIVE,
        target_allocation={
            AssetClass.EQUITIES: 0.25,
            AssetClass.BONDS: 0.55,
            AssetClass.CASH: 0.15,
            AssetClass.ALTERNATIVES: 0.05,
        },
    ),
}

HOLDINGS: dict[str, list[Holding]] = {
    "NB-1001": [
        Holding(fund_id="NBG-EQ01", fund_name="Northbridge Global Equity Fund", asset_class=AssetClass.EQUITIES, market_value_usd=65_000),
        Holding(fund_id="NBG-BD01", fund_name="Northbridge Short Duration Bond Fund", asset_class=AssetClass.BONDS, market_value_usd=25_000),
        Holding(fund_id="NBG-CASH", fund_name="Northbridge Cash Reserve", asset_class=AssetClass.CASH, market_value_usd=5_000),
        Holding(fund_id="NBG-ALT01", fund_name="Northbridge Diversified Alternatives Fund", asset_class=AssetClass.ALTERNATIVES, market_value_usd=5_000),
    ],
    "NB-1002": [
        Holding(fund_id="NBG-EQ02", fund_name="Northbridge Balanced Growth Fund", asset_class=AssetClass.EQUITIES, market_value_usd=180_000),
        Holding(fund_id="NBG-BD01", fund_name="Northbridge Short Duration Bond Fund", asset_class=AssetClass.BONDS, market_value_usd=30_000),
        Holding(fund_id="NBG-CASH", fund_name="Northbridge Cash Reserve", asset_class=AssetClass.CASH, market_value_usd=15_000),
        Holding(fund_id="NBG-ALT01", fund_name="Northbridge Diversified Alternatives Fund", asset_class=AssetClass.ALTERNATIVES, market_value_usd=25_000),
    ],
    "NB-1003": [
        Holding(fund_id="NBG-EQ01", fund_name="Northbridge Global Equity Fund", asset_class=AssetClass.EQUITIES, market_value_usd=100_000),
        Holding(fund_id="NBG-BD01", fund_name="Northbridge Short Duration Bond Fund", asset_class=AssetClass.BONDS, market_value_usd=220_000),
        Holding(fund_id="NBG-CASH", fund_name="Northbridge Cash Reserve", asset_class=AssetClass.CASH, market_value_usd=60_000),
        Holding(fund_id="NBG-ALT01", fund_name="Northbridge Diversified Alternatives Fund", asset_class=AssetClass.ALTERNATIVES, market_value_usd=20_000),
    ],
}


def list_client_ids() -> list[str]:
    """Return all seeded client ids, for the frontend's client picker."""
    return list(CLIENTS.keys())
