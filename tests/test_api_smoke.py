"""Smoke tests for the FastAPI app: health/readiness endpoints, the client list,
and a full streaming chat round-trip through the real HTTP layer (still fully
offline, since no OPENAI_API_KEY is set in the test environment).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_and_readyz() -> None:
    app = create_app()
    with TestClient(app) as client:
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        ready = client.get("/readyz")
        assert ready.status_code == 200
        body = ready.json()
        assert body["mock_mode"] is True
        assert body["fund_factsheets_loaded"] >= 1


def test_list_clients() -> None:
    app = create_app()
    with TestClient(app) as client:
        res = client.get("/api/clients")
        assert res.status_code == 200
        client_ids = {c["client_id"] for c in res.json()}
        assert {"NB-1001", "NB-1002", "NB-1003"}.issubset(client_ids)


def test_chat_stream_unknown_client_returns_404() -> None:
    app = create_app()
    with TestClient(app) as client:
        res = client.post("/api/chat/NOT-A-CLIENT/stream", json={"message": "hi"})
        assert res.status_code == 404


def test_chat_stream_happy_path_contains_sse_events() -> None:
    app = create_app()
    with TestClient(app) as client:
        res = client.post("/api/chat/NB-1001/stream", json={"message": "What are my current holdings?"})
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        body = res.text
        assert "event: tool_call" in body
        assert "event: token" in body
        assert "event: done" in body


def test_metrics_endpoint_exposes_prometheus_format() -> None:
    app = create_app()
    with TestClient(app) as client:
        res = client.get("/metrics")
        assert res.status_code == 200
        assert b"assistant_runs_total" in res.content or "assistant_runs_total" in res.text
