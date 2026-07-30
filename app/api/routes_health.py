"""Health, readiness, and metrics endpoints.

`/healthz`  -- liveness: is the process up at all (used by k8s livenessProbe).
`/readyz`   -- readiness: are dependencies (fund fact sheets loaded, audit log
               path writable) actually usable (used by k8s readinessProbe).
`/metrics`  -- Prometheus text-format scrape endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.api.schemas import HealthResponse, ReadyResponse
from app.infrastructure.metrics import render_latest

router = APIRouter(tags=["ops"])


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=ReadyResponse)
def readyz(request: Request) -> ReadyResponse:
    settings = request.app.state.settings
    factsheet_store = request.app.state.factsheet_store
    return ReadyResponse(
        status="ready",
        mock_mode=settings.is_mock_mode,
        fund_factsheets_loaded=len(factsheet_store.file_paths),
    )


@router.get("/metrics")
def metrics() -> Response:
    body, content_type = render_latest()
    return Response(content=body, media_type=content_type)
