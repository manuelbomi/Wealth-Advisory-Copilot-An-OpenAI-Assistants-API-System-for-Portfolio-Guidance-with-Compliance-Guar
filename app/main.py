"""Application entrypoint / composition root.

`create_app()` builds the FastAPI app and wires the full dependency graph (config
-> fund fact-sheet store -> Assistants client (mock or real) -> guardrail -> audit
log -> AdvisoryService), then stashes the composed objects on `app.state` so route
handlers can retrieve them via `app/api/dependencies.py`. This is the only module
that is allowed to *construct* infrastructure singletons; everything downstream
just consumes them.

Run locally with:  uvicorn app.main:app --reload   (or `make run`)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.domain.exceptions import ClientNotFoundError
from app.guardrails.suitability_guardrail import SuitabilityGuardrail
from app.infrastructure.audit_log import AuditLogWriter
from app.infrastructure.client_factory import get_assistants_client
from app.infrastructure.fund_factsheet_store import FundFactsheetStore
from app.service.advisory_service import AdvisoryService

logger = logging.getLogger("app.main")

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STATIC_DIR = _REPO_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Compose the dependency graph once at process startup."""
    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    factsheet_store = FundFactsheetStore(directory=settings.fund_factsheets_dir)
    assistants_client = get_assistants_client(settings, factsheet_store)
    guardrail = SuitabilityGuardrail()
    audit_log_writer = AuditLogWriter(path=settings.audit_log_path)
    advisory_service = AdvisoryService(
        assistants_client=assistants_client,
        guardrail=guardrail,
        audit_log_writer=audit_log_writer,
    )

    app.state.settings = settings
    app.state.factsheet_store = factsheet_store
    app.state.assistants_client = assistants_client
    app.state.guardrail = guardrail
    app.state.audit_log_writer = audit_log_writer
    app.state.advisory_service = advisory_service

    logger.info(
        "app_started",
        extra={"mock_mode": settings.is_mock_mode, "environment": settings.environment},
    )
    yield
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Wealth Advisory Copilot",
        description=(
            "Demo OpenAI Assistants API system for portfolio guidance with compliance "
            "guardrails. All data is synthetic; 'Northbridge Financial Group' is a "
            "fictional bank brand. Not real investment advice."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(chat_router)

    @app.exception_handler(ClientNotFoundError)
    async def _client_not_found_handler(_request, exc: ClientNotFoundError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=404, content={"detail": str(exc)})

    if _STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")

    return app


app = create_app()
