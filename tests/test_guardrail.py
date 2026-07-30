"""Covers the suitability guardrail: it must block a crafted risky message,
annotate a crafted individualized-recommendation message (including via the
fallback heuristic classifier for phrasing not on the explicit pattern list), and
pass a compliant message through unchanged.
"""

from __future__ import annotations

from app.domain.models import GuardrailAction
from app.guardrails.suitability_guardrail import DISCLAIMER_MARKER, SuitabilityGuardrail


def test_guardrail_blocks_guaranteed_return_language(guardrail: SuitabilityGuardrail) -> None:
    risky = "This fund offers a guaranteed return with no risk at all, so it's a sure thing."
    decision = guardrail.evaluate(risky)

    assert decision.action == GuardrailAction.BLOCKED
    assert "guaranteed_outcome" in decision.matched_patterns
    # The original risky claim must not survive in the output.
    assert "guaranteed return" not in decision.output_text.lower()


def test_guardrail_annotates_explicit_directive_language(guardrail: SuitabilityGuardrail) -> None:
    risky = "You should buy the Northbridge Balanced Growth Fund today."
    decision = guardrail.evaluate(risky)

    assert decision.action == GuardrailAction.ANNOTATED
    assert "directive_you_should" in decision.matched_patterns
    assert risky in decision.output_text  # original message preserved
    assert DISCLAIMER_MARKER in decision.output_text.lower()


def test_guardrail_annotates_via_fallback_classifier(guardrail: SuitabilityGuardrail) -> None:
    # Phrasing that doesn't match any explicit caution regex but is clearly a
    # personal directive ("you ... move ...") -- exercises the tier-2 fallback.
    risky = "You could always move your account toward safer options."
    decision = guardrail.evaluate(risky)

    assert decision.action == GuardrailAction.ANNOTATED
    assert "fallback_classifier" in decision.matched_patterns


def test_guardrail_passes_compliant_message_unchanged(guardrail: SuitabilityGuardrail) -> None:
    compliant = (
        "The Northbridge Balanced Growth Fund's objective is long-term capital "
        "appreciation with a secondary focus on income, targeting moderate risk."
    )
    decision = guardrail.evaluate(compliant)

    assert decision.action == GuardrailAction.PASS
    assert decision.output_text == compliant
    assert decision.matched_patterns == []


def test_guardrail_does_not_duplicate_existing_disclaimer(guardrail: SuitabilityGuardrail) -> None:
    already_disclosed = (
        "You should buy the Northbridge Balanced Growth Fund today. "
        "This information is for educational purposes only and "
        f"{DISCLAIMER_MARKER}."
    )
    decision = guardrail.evaluate(already_disclosed)

    assert decision.action == GuardrailAction.PASS
    assert decision.output_text == already_disclosed
