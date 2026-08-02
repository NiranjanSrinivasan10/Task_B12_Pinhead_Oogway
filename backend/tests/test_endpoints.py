"""
tests/test_endpoints.py
~~~~~~~~~~~~~~~~~~~~~~~~
Offline endpoint tests — validate routing, schema, and error-handling logic
without a live database.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.database import get_db


@pytest.fixture(scope="module")
def app():
    from app.main import app as _app
    return _app


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ─── /health ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_health_returns_200(client):
    with (
        patch("app.routers.health.check_db_connection", new=AsyncMock(return_value=True)),
        patch("app.routers.health._check_ollama", new=AsyncMock(return_value=(True, "reachable"))),
    ):
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["db"] is True
    assert "status" in data
    assert "ollama" in data
    assert "pi_subprocess" in data


@pytest.mark.anyio
async def test_health_degraded_when_ollama_down(client):
    with (
        patch("app.routers.health.check_db_connection", new=AsyncMock(return_value=True)),
        patch("app.routers.health._check_ollama", new=AsyncMock(return_value=(False, "connection refused"))),
    ):
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ollama"] is False
    assert data["status"] in ("degraded", "unhealthy")


# ─── /sessions ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_create_session_schema(client):
    """POST /sessions must return 422 for invalid provider."""
    resp = await client.post(
        "/sessions",
        json={"title": "Test", "llm_provider": "invalid_provider"},
    )
    assert resp.status_code == 422  # Pydantic validation error


@pytest.mark.anyio
async def test_create_session_valid_schema(app, client):
    """POST /sessions with valid body creates session."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    async def fake_refresh(obj):
        obj.id = uuid.uuid4()
        obj.created_at = "2026-07-31T12:00:00Z"
        obj.updated_at = "2026-07-31T12:00:00Z"
        obj.messages = []

    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    async def fake_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = fake_get_db

    try:
        resp = await client.post(
            "/sessions",
            json={"title": "My Session", "llm_provider": "openai", "llm_model": "gpt-4o-mini"},
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "My Session"
    finally:
        app.dependency_overrides.clear()


# ─── Missing API key → 422 ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_missing_api_key_returns_422(app, client):
    """
    POST /sessions/{id}/messages with openai provider but no OPENAI_API_KEY
    must return 422 with code=missing_api_key BEFORE opening an SSE stream.
    """
    fake_session_id = uuid.uuid4()
    fake_session = MagicMock()
    fake_session.id = fake_session_id
    fake_session.llm_provider = "openai"
    fake_session.llm_model = "gpt-4o-mini"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_session
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def fake_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = fake_get_db

    try:
        with patch("app.routers.messages.settings") as mock_settings:
            mock_settings.require_provider_key.side_effect = ValueError(
                "OPENAI_API_KEY is not set."
            )
            mock_settings.openai_api_key = ""

            resp = await client.post(
                f"/sessions/{fake_session_id}/messages",
                json={"content": "What is PMF?"},
            )

        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "missing_api_key"
    finally:
        app.dependency_overrides.clear()


# ─── OpenAPI schema ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_openapi_schema_has_all_routes(client):
    """Verify all 7 documented routes appear in the OpenAPI schema."""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]

    required = [
        "/sessions",
        "/sessions/{session_id}",
        "/sessions/{session_id}/config",
        "/sessions/{session_id}/messages",
        "/artifacts/{artifact_id}",
        "/health",
    ]
    for path in required:
        assert path in paths, f"Missing route in OpenAPI schema: {path}"


# ─── /sessions/{id} 404 ────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_session_not_found(app, client):
    """GET /sessions/{random-uuid} should return 404 when session doesn't exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def fake_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = fake_get_db

    try:
        resp = await client.get(f"/sessions/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# ─── /artifacts/{id} 404 ──────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_artifact_not_found(app, client):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def fake_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = fake_get_db

    try:
        resp = await client.get(f"/artifacts/{uuid.uuid4()}")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
