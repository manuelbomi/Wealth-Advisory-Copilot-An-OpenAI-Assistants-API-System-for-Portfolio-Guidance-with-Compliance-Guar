"""Service layer: orchestrates a full chat turn.

`AdvisoryService.handle_chat_turn` is the one place that wires together the
Assistants client (mock or real), the tool-call loop, the suitability guardrail,
audit logging, and metrics -- the API layer just adapts this to HTTP/SSE, and the
infrastructure layer just executes individual calls. Keeping this orchestration in
its own layer (rather than inline in a FastAPI route) is what makes it possible to
unit-test the whole "run -> guardrail -> audit log" pipeline without spinning up
an HTTP server.
"""
