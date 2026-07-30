"""Assistants client interface.

Both `MockAssistantsClient` and `OpenAIAssistantsClient` implement this Protocol.
The service layer (`app.service.advisory_service`) only ever depends on this
interface, never on a concrete implementation -- that is what makes swapping mock
for real behind the `OPENAI_API_KEY` env var a one-line change in
`client_factory.py` with zero blast radius elsewhere.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from app.domain.models import ChatEvent


class AssistantsClient(Protocol):
    """Structural interface for anything that can run an Assistants-style
    thread/run/tool-call turn."""

    def ensure_thread(self, client_id: str) -> str:
        """Return the persistent thread id for a client, creating one if needed."""
        ...

    def run_turn(self, client_id: str, thread_id: str, user_message: str) -> AsyncIterator[ChatEvent]:
        """Run one assistant turn end-to-end (submitting the user message, handling
        any tool calls the model requests, and producing a final assistant message),
        yielding `ChatEvent`s as it goes. The final yielded event must have
        `type == ChatEventType.DONE` and carry the final assistant text plus a
        structured list of tool calls in `data`, so the service layer can apply the
        guardrail and write the audit log entry.
        """
        ...
