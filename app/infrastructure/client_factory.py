"""Selects the mock or real Assistants client based on configuration.

This is the single seam that implements the "no paid API keys required" promise:
absence of `OPENAI_API_KEY` (checked via `settings.is_mock_mode`) transparently
swaps in `MockAssistantsClient`. Every other layer of the app depends only on the
`AssistantsClient` Protocol, so this function is the only place that branches on
"are we live or offline".
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.infrastructure.assistants_client import AssistantsClient
from app.infrastructure.fund_factsheet_store import FundFactsheetStore
from app.infrastructure.mock_assistants_client import MockAssistantsClient

logger = logging.getLogger("client_factory")


def get_assistants_client(settings: Settings, factsheet_store: FundFactsheetStore) -> AssistantsClient:
    if settings.is_mock_mode:
        logger.info("assistants_client_selected", extra={"mode": "mock"})
        return MockAssistantsClient(factsheet_store=factsheet_store)

    logger.info("assistants_client_selected", extra={"mode": "live_openai"})
    from app.infrastructure.openai_assistants_client import OpenAIAssistantsClient

    return OpenAIAssistantsClient(settings=settings, factsheet_store=factsheet_store)
