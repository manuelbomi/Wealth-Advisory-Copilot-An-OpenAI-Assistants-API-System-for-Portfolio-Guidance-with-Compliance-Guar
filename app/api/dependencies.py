"""FastAPI dependency-injection wiring.

All long-lived singletons (settings, the fund fact-sheet store, the Assistants
client, the guardrail, the audit log writer, and the composed AdvisoryService) are
built once in `app.main`'s startup hook and stashed on `app.state`. These `Depends`
functions just fetch them back out of `request.app.state` -- this keeps route
handlers thin and makes the whole dependency graph swappable in tests (see
tests/conftest.py, which overrides `get_advisory_service`).
"""

from __future__ import annotations

from fastapi import Request

from app.infrastructure.audit_log import AuditLogWriter
from app.service.advisory_service import AdvisoryService


def get_advisory_service(request: Request) -> AdvisoryService:
    return request.app.state.advisory_service


def get_audit_log_writer(request: Request) -> AuditLogWriter:
    return request.app.state.audit_log_writer
