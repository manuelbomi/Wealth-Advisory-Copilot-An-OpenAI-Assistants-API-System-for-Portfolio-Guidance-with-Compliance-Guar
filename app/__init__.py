"""Wealth Advisory Copilot application package.

This package implements a layered architecture:

    app/api             -> HTTP boundary (FastAPI routers, request/response schemas)
    app/service          -> use-case orchestration (the Assistants thread/run/tool loop,
                             guardrail application, audit logging)
    app/domain           -> pure business models and synthetic seed data (no I/O)
    app/infrastructure   -> external integrations (OpenAI SDK, mock client, audit log
                             storage, fund fact-sheet retrieval, circuit breaker, metrics)
    app/tools            -> function-calling tool implementations exposed to the assistant
    app/guardrails        -> compliance/suitability guardrail middleware
    app/core             -> cross-cutting concerns (settings, logging, tracing)

Everything here is entirely synthetic / for demonstration purposes only. See the
top-level README.md for the fictional bank disclaimer and governance notes.
"""
