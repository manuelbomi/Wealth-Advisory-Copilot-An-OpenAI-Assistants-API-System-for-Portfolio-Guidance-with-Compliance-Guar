# Governance & Guardrails

> This document describes an **illustrative, simplified pattern** built for a
> portfolio project. It is explicitly **not** a certified compliance control, has
> not been reviewed by legal/compliance/risk functions, and must not be
> represented as satisfying any real regulatory suitability obligation
> (e.g. FINRA Reg BI, MiFID II suitability, or equivalent). All client, portfolio,
> and fund data in this repository is synthetic; "Northbridge Financial Group" is
> a fictional bank name used only to make the demo concrete.

## What the guardrail does

`app/guardrails/suitability_guardrail.py` implements `SuitabilityGuardrail`, which
runs over every candidate outgoing assistant message **before** it is shown to the
user (see `AdvisoryService.handle_chat_turn`). It has three possible outcomes:

| Action      | Trigger                                                                 | Effect                                                             |
|-------------|--------------------------------------------------------------------------|---------------------------------------------------------------------|
| `PASS`      | No risky language detected                                               | Message sent unchanged                                              |
| `ANNOTATED` | Individualized-sounding directive language ("you should buy...")         | Standard compliance disclaimer is appended                          |
| `BLOCKED`   | Language implying a guaranteed or risk-free outcome ("guaranteed return") | Message is replaced entirely with a safe explanation + disclaimer   |

Detection is two-tiered:

1. **Deterministic regex/keyword heuristics** (`_BLOCK_PATTERNS`,
   `_CAUTION_PATTERNS`) -- fast, fully explainable, and unit-tested
   (`tests/test_guardrail.py`). This tier decides the outcome for any message that
   matches a known pattern.
2. **Fallback classifier** (`HeuristicFallbackClassifier`) -- only consulted when
   tier 1 finds nothing, to catch paraphrased directive language the fixed pattern
   list misses. In this repo the fallback is a small dependency-free heuristic
   (proximity of "you/your" to a finance-action verb) so the whole guardrail stays
   deterministic and runnable in CI with zero API calls. `LlmSuitabilityClassifier`
   in the same module documents the extension point for swapping in a real
   model-based classification call in a live deployment.

## Why buffer instead of stream-then-check

The guardrail evaluates the *complete* candidate message, not a token stream. A
compliance check cannot meaningfully evaluate half a sentence, and un-vetted
partial output should never reach a user in a regulated context. The trade-off
(discussed in the README) is that the UI's "streaming" effect is actually the
already-approved message being re-chunked and sent out after the fact, not raw
provider token deltas.

## Audit trail

Every run appends one entry to the audit log
(`app/infrastructure/audit_log.py`, default path `logs/audit_log.jsonl`)
containing: timestamp, correlation/run id, thread id, client id, the user's
message, a summary of every tool call and its result, and the guardrail action
taken with its reason. Tool result payloads are stored as truncated summaries, not
full raw payloads, to avoid the audit log becoming an uncontrolled second copy of
sensitive data.

## Known limitations (be honest about these in an interview)

- **Not certified.** This is a demonstration of the *pattern* of a guardrail in an
  agentic pipeline, not a substitute for a real suitability/compliance engine, and
  it has not been validated against any real regulatory framework.
- **Regex is brittle.** It will miss cleverly-phrased risky language and can
  false-positive on benign phrasing that happens to match a pattern. A production
  system would want a properly trained/evaluated classifier, human-in-the-loop
  review for edge cases, and ongoing red-teaming.
- **No real identity/authorization.** `client_id` is passed as a path parameter
  with no authentication -- a real system needs proper authN/authZ so a caller can
  only access their own (or their book of business's) clients.
- **Append-only file, not a tamper-evident ledger.** The audit log is a local
  JSONL file for demo purposes. Production would want WORM storage, hash-chaining
  or a dedicated audit service, and a defined retention policy.
- **English-only, keyword-based.** No multilingual support, and no semantic
  understanding beyond simple keyword/proximity heuristics.

## What a production version would add

- A reviewed, versioned policy document mapping each guardrail rule to a specific
  compliance requirement, owned by legal/compliance, with a change-review process.
- A real model-based (or ensemble) classifier with measured precision/recall on a
  labeled evaluation set, plus periodic re-evaluation.
- Human escalation path for `BLOCKED` outcomes (route to a licensed advisor rather
  than just re-prompting).
- Tamper-evident audit storage and SIEM integration.
- Role-based access control on which client_ids a given caller may query.
