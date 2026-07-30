"""Suitability guardrail: detects individualized-recommendation and
guaranteed-outcome language in outgoing assistant messages.

IMPORTANT -- read GOVERNANCE.md. This is a deliberately simple, illustrative
pattern for a portfolio project. It is NOT a certified suitability / compliance
control and must not be presented or relied on as one in any real regulated
context.

Two-tier design:

  1. Deterministic regex/keyword heuristics (fast, explainable, unit-testable) --
     this is the tier that actually decides BLOCKED vs ANNOTATED vs PASS in this
     demo, precisely so behavior is reproducible offline without any model call.

  2. An LLM-based classifier *fallback*, only consulted when the regex tier finds
     no explicit match, to catch paraphrased individualized-recommendation language
     the fixed pattern list misses (e.g. "the smart move for your situation is..").
     In mock/offline mode this falls back further to a cheap local heuristic
     (`HeuristicFallbackClassifier`) so the whole guardrail remains deterministic
     and free to run in CI. When `OPENAI_API_KEY` is configured, a real
     classifier call could be substituted by swapping the `classifier=` argument
     -- see `LlmSuitabilityClassifier` below for the integration point.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

from app.domain.models import GuardrailAction, GuardrailDecision

logger = logging.getLogger("guardrail")

# Substring used to detect "the standard disclaimer is already present" so we never
# stack duplicate disclaimers onto a message across multiple guardrail passes.
DISCLAIMER_MARKER = "does not constitute individualized investment advice"

STANDARD_DISCLAIMER = (
    "⚠️ Compliance note: This information is for educational purposes only and "
    "does not constitute individualized investment advice. It does not account for your "
    "complete financial picture. Please consult a licensed financial advisor before "
    "making any investment decision. Northbridge Financial Group is a fictional "
    "brand used for demonstration purposes only."
)

BLOCKED_REPROMPT_MESSAGE = (
    "I can't provide that response as written because it appears to promise a "
    "guaranteed or risk-free investment outcome, which this system's compliance "
    "guardrail does not allow -- no investment can be guaranteed. I can instead "
    "share factual, educational information about funds, allocations, and your "
    "risk profile. " + STANDARD_DISCLAIMER
)

# --- Tier 1: deterministic patterns -----------------------------------------------

# Hard-block patterns: language implying certainty/safety that is never appropriate
# to send unmodified, regardless of any disclaimer appended after the fact.
_BLOCK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("guaranteed_outcome", re.compile(r"\bguarantee[sd]?\b[^.?!]{0,40}\b(return|profit|gain|income|outcome)\b", re.IGNORECASE)),
    ("risk_free_claim", re.compile(r"\brisk[- ]free\b", re.IGNORECASE)),
    ("cannot_lose_claim", re.compile(r"\b(can'?t|cannot|won'?t)\s+lose\b", re.IGNORECASE)),
    ("promised_profit", re.compile(r"\bpromise[sd]?\b[^.?!]{0,40}\b(profit|return|gain)\b", re.IGNORECASE)),
]

# Caution patterns: individualized-sounding recommendation/directive language. These
# do not block the message but trigger auto-appending the standard disclaimer if one
# is not already present.
_CAUTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("directive_you_should", re.compile(r"\byou should\s+(buy|sell|invest|purchase|move|allocate)\b", re.IGNORECASE)),
    ("directive_you_must", re.compile(r"\byou must\s+(buy|sell|invest|purchase|move|allocate)\b", re.IGNORECASE)),
    ("directive_you_need_to", re.compile(r"\byou need to\s+(buy|sell|invest|purchase|move|allocate)\b", re.IGNORECASE)),
    ("first_person_recommendation", re.compile(r"\bi recommend\b", re.IGNORECASE)),
    ("best_for_you", re.compile(r"\bbest\s+(investment|fund|choice|option)s?\s+for you\b", re.IGNORECASE)),
]

# Minimum fallback-classifier score (0-1) required to trigger an ANNOTATED action
# when neither the block nor caution regex tier matched anything.
_FALLBACK_THRESHOLD = 0.5


class SuitabilityClassifier(Protocol):
    """Interface for the tier-2 fallback classifier.

    Any implementation just needs to return a 0.0-1.0 "looks like an individualized
    recommendation" score for a chunk of assistant-generated text.
    """

    def score(self, text: str) -> float: ...


class HeuristicFallbackClassifier:
    """Deterministic, dependency-free stand-in for an LLM classifier.

    Scores text by proximity of second-person pronouns ("you"/"your") to
    finance-action verbs within a short token window -- a cheap approximation of
    "is this addressed at the reader as a personal directive". Used automatically
    in offline/mock mode and as the default even in live mode, so this guardrail's
    outcome stays deterministic and unit-testable; see `LlmSuitabilityClassifier`
    for how a real model call would be substituted in production.
    """

    _PROXIMITY_PATTERN = re.compile(
        r"\byou(?:r)?\b[^.?!]{0,30}\b(buy|sell|invest|purchase|allocate|move|switch|rebalance)\b",
        re.IGNORECASE,
    )

    def score(self, text: str) -> float:
        matches = self._PROXIMITY_PATTERN.findall(text)
        if not matches:
            return 0.0
        # Cap contribution so a wall of matches doesn't blow past 1.0; two or more
        # proximity hits is already strong enough signal to annotate.
        return min(1.0, 0.5 * len(matches))


class LlmSuitabilityClassifier:
    """Production integration point for a real model-based classifier fallback.

    Not exercised in tests or offline mode (kept intentionally thin). Wire this up
    to a cheap classification call (e.g. a short structured-output chat completion
    asking "does this text give an individualized investment recommendation?
    yes/no") when `OPENAI_API_KEY` is configured, if the regex tiers prove
    insufficient in a real deployment.
    """

    def __init__(self, openai_client: object) -> None:
        self._client = openai_client

    def score(self, text: str) -> float:  # pragma: no cover - illustrative only
        raise NotImplementedError(
            "LlmSuitabilityClassifier is a documented extension point, not wired "
            "up in this demo -- HeuristicFallbackClassifier is used by default so "
            "the guardrail stays deterministic offline."
        )


class SuitabilityGuardrail:
    """Evaluates a candidate outgoing assistant message and decides what to do.

    Returns a `GuardrailDecision` with one of three actions:

      PASS      -- message is unchanged.
      ANNOTATED -- message is unchanged except the standard disclaimer is appended.
      BLOCKED   -- message is replaced entirely with a safe re-prompt explaining why.
    """

    def __init__(self, classifier: SuitabilityClassifier | None = None) -> None:
        self._classifier = classifier or HeuristicFallbackClassifier()

    def evaluate(self, text: str) -> GuardrailDecision:
        matched_block = [name for name, pattern in _BLOCK_PATTERNS if pattern.search(text)]
        if matched_block:
            logger.warning("guardrail_blocked", extra={"matched_patterns": matched_block})
            return GuardrailDecision(
                action=GuardrailAction.BLOCKED,
                output_text=BLOCKED_REPROMPT_MESSAGE,
                matched_patterns=matched_block,
                reason=(
                    "Blocked: message contains language implying a guaranteed or "
                    "risk-free investment outcome."
                ),
            )

        already_disclosed = DISCLAIMER_MARKER.lower() in text.lower()
        matched_caution = [name for name, pattern in _CAUTION_PATTERNS if pattern.search(text)]

        if matched_caution and not already_disclosed:
            logger.info("guardrail_annotated", extra={"matched_patterns": matched_caution})
            return GuardrailDecision(
                action=GuardrailAction.ANNOTATED,
                output_text=f"{text.rstrip()}\n\n{STANDARD_DISCLAIMER}",
                matched_patterns=matched_caution,
                reason="Annotated: message contains individualized-sounding recommendation language.",
            )

        if not already_disclosed:
            score = self._classifier.score(text)
            if score >= _FALLBACK_THRESHOLD:
                logger.info("guardrail_annotated_fallback", extra={"classifier_score": score})
                return GuardrailDecision(
                    action=GuardrailAction.ANNOTATED,
                    output_text=f"{text.rstrip()}\n\n{STANDARD_DISCLAIMER}",
                    matched_patterns=["fallback_classifier"],
                    reason=f"Annotated: fallback classifier score {score:.2f} met threshold {_FALLBACK_THRESHOLD}.",
                )

        return GuardrailDecision(action=GuardrailAction.PASS, output_text=text, matched_patterns=[], reason="")
