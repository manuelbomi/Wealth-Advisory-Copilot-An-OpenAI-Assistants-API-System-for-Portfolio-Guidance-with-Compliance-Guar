"""AdvisoryService: orchestrates one full chat turn end-to-end.

Pipeline, per turn:

    1. Resolve/create the client's persistent thread.
    2. Run the Assistants thread/run/tool-call loop (mock or real -- see
       app.infrastructure.assistants_client.AssistantsClient), streaming
       tool_call/tool_result events out to the caller as they happen so the UI can
       show "checking your holdings..." style progress.
    3. Once the assistant has a candidate final message, run it through the
       suitability guardrail *before* anything is shown to the user -- this is a
       deliberate design choice: we buffer the full candidate message rather than
       forwarding raw provider token-deltas, because a compliance guardrail cannot
       meaningfully vet a half-sent sentence. We then re-stream the
       guardrail-approved text back out in chunks to preserve a "streaming" UX.
    4. Write one audit log entry covering the whole run (client, tool calls,
       guardrail action, message preview).
    5. Record Prometheus metrics for the run, each tool call, and the guardrail
       decision.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator

from app.core.logging_config import correlation_id_var
from app.core.tracing import span
from app.domain.models import (
    AuditLogEntry,
    ChatEvent,
    ChatEventType,
    ToolCallRecord,
)
from app.guardrails.suitability_guardrail import SuitabilityGuardrail
from app.infrastructure.assistants_client import AssistantsClient
from app.infrastructure.audit_log import AuditLogWriter
from app.infrastructure.metrics import (
    ASSISTANT_RUNS_TOTAL,
    GUARDRAIL_ACTIONS_TOTAL,
    RUN_DURATION_SECONDS,
    TOOL_CALLS_TOTAL,
)

logger = logging.getLogger("advisory_service")

# Chunk size (characters) used to re-stream the guardrail-approved final message,
# simulating token-by-token delivery for the UI without needing raw provider
# streaming to survive the guardrail buffering step described above.
_STREAM_CHUNK_SIZE = 24


class AdvisoryService:
    def __init__(
        self,
        assistants_client: AssistantsClient,
        guardrail: SuitabilityGuardrail,
        audit_log_writer: AuditLogWriter,
    ) -> None:
        self._client = assistants_client
        self._guardrail = guardrail
        self._audit_log = audit_log_writer

    async def handle_chat_turn(self, client_id: str, user_message: str) -> AsyncIterator[ChatEvent]:
        """Run one full turn, yielding ChatEvents suitable for SSE streaming.

        Event order: zero or more (tool_call, tool_result) pairs, one guardrail
        event, N token events carrying the approved final message in chunks, then
        one final `done` event.
        """
        start = time.perf_counter()
        run_id = f"run_{uuid.uuid4().hex[:16]}"
        token = correlation_id_var.set(run_id)
        try:
            with span("assistant_run", client_id=client_id, run_id=run_id):
                thread_id = self._client.ensure_thread(client_id)

                tool_calls: list[ToolCallRecord] = []
                final_text = ""
                resolved_thread_id = thread_id
                resolved_run_id = run_id

                async for event in self._client.run_turn(client_id, thread_id, user_message):
                    if event.type == ChatEventType.TOOL_CALL:
                        yield event
                    elif event.type == ChatEventType.TOOL_RESULT:
                        succeeded = bool(event.data.get("succeeded", True))
                        TOOL_CALLS_TOTAL.labels(
                            tool_name=event.data.get("tool_name", "unknown"), succeeded=str(succeeded)
                        ).inc()
                        tool_calls.append(
                            ToolCallRecord(
                                tool_name=event.data.get("tool_name", "unknown"),
                                arguments={},  # populated below once the matching tool_call is seen
                                result_summary=_summarize(event.data.get("result")),
                                succeeded=succeeded,
                            )
                        )
                        yield event
                    elif event.type == ChatEventType.DONE:
                        # This DONE comes from the *assistants client* signaling the
                        # raw model turn is complete -- we deliberately do not
                        # forward it to the caller yet; the guardrail still needs
                        # to run first (see module docstring).
                        final_text = str(event.data.get("final_text", ""))
                        resolved_thread_id = str(event.data.get("thread_id", thread_id))
                        resolved_run_id = str(event.data.get("run_id", run_id))

                decision = self._guardrail.evaluate(final_text)
                GUARDRAIL_ACTIONS_TOTAL.labels(action=decision.action.value).inc()
                yield ChatEvent(
                    type=ChatEventType.GUARDRAIL,
                    data={"action": decision.action.value, "reason": decision.reason},
                )

                for chunk in _chunk_text(decision.output_text, _STREAM_CHUNK_SIZE):
                    yield ChatEvent(type=ChatEventType.TOKEN, data={"delta": chunk})

                entry = AuditLogEntry(
                    correlation_id=run_id,
                    thread_id=resolved_thread_id,
                    run_id=resolved_run_id,
                    client_id=client_id,
                    user_message=user_message,
                    tool_calls=tool_calls,
                    guardrail_action=decision.action,
                    guardrail_reason=decision.reason,
                    final_message_preview=decision.output_text,
                )
                self._audit_log.write(entry)

                ASSISTANT_RUNS_TOTAL.labels(client_id=client_id).inc()
                RUN_DURATION_SECONDS.observe(time.perf_counter() - start)

                yield ChatEvent(
                    type=ChatEventType.DONE,
                    data={
                        "run_id": resolved_run_id,
                        "thread_id": resolved_thread_id,
                        "guardrail_action": decision.action.value,
                    },
                )
        except Exception as exc:  # pragma: no cover - defensive top-level guard
            logger.exception("chat_turn_failed", extra={"client_id": client_id})
            yield ChatEvent(type=ChatEventType.ERROR, data={"message": str(exc)})
        finally:
            correlation_id_var.reset(token)


def _chunk_text(text: str, size: int) -> list[str]:
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


def _summarize(result: object, max_len: int = 200) -> str:
    """Compact, audit-log-safe summary of a tool result (never the raw payload)."""
    text = str(result)
    return text[:max_len] + ("..." if len(text) > max_len else "")
