"""Shared pytest fixtures.

Everything here runs fully offline: the fund fact-sheet store reads the real
synthetic `.txt` files shipped in the repo (no network), and the audit log is
pointed at a pytest tmp_path so tests never write into the repo's real
`logs/audit_log.jsonl`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.guardrails.suitability_guardrail import SuitabilityGuardrail
from app.infrastructure.audit_log import AuditLogWriter
from app.infrastructure.fund_factsheet_store import FundFactsheetStore
from app.infrastructure.mock_assistants_client import MockAssistantsClient
from app.service.advisory_service import AdvisoryService

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FACTSHEETS_DIR = _REPO_ROOT / "data" / "fund_factsheets"


@pytest.fixture(autouse=True)
def _force_offline_mock_mode(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make the test suite hermetic against the *host machine's* environment.

    This project's entire premise is "runs fully offline, no paid API key
    required" -- tests must exercise that path deterministically regardless of
    whether the developer/CI machine happens to have an unrelated OPENAI_API_KEY
    set in its shell for other tools. We strip it for the duration of each test
    and clear the cached Settings singleton so `get_settings()` re-reads a clean
    environment.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def factsheet_store() -> FundFactsheetStore:
    return FundFactsheetStore(directory=_FACTSHEETS_DIR)


@pytest.fixture
def mock_client(factsheet_store: FundFactsheetStore) -> MockAssistantsClient:
    return MockAssistantsClient(factsheet_store=factsheet_store)


@pytest.fixture
def guardrail() -> SuitabilityGuardrail:
    return SuitabilityGuardrail()


@pytest.fixture
def audit_log_writer(tmp_path: Path) -> AuditLogWriter:
    return AuditLogWriter(path=tmp_path / "audit_log.jsonl")


@pytest.fixture
def advisory_service(
    mock_client: MockAssistantsClient,
    guardrail: SuitabilityGuardrail,
    audit_log_writer: AuditLogWriter,
) -> AdvisoryService:
    return AdvisoryService(
        assistants_client=mock_client,
        guardrail=guardrail,
        audit_log_writer=audit_log_writer,
    )
