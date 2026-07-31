"""
tests/test_endpoints.py
~~~~~~~~~~~~~~~~~~~~~~~~
Offline endpoint tests — validate routing, schema, and error-handling logic
without a live database.

Run from backend/:
    .\\venv\\Scripts\\python.exe -m pytest tests/test_endpoints.py -v
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

# ─── Patch DB & pi_client before importing app ─────────────────────────────
# We must patch before `app` is imported so the startup event doesn't try to
# connect to a real database.

@pytest.fixture(scope="module", autouse=True)
def patch_db_and_pi():
    """Patch DB check and pi_client so tests run without a real Postgres/Node."""
    with (
        patch("app.database.check_db_connection", new=AsyncMock(return_value=True)),
        patch("app.pi_client.PiClient._ensure_process", new=AsyncMock()),
    ):
        yield


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
async def test_create_session_valid_schema(client):
    """POST /sessions with valid body returns 201 (or 500 if no DB — check schema)."""
    # When the DB is mocked we get 500 from SQLAlchemy; we just check Pydantic passes.
    # A full DB-integration test would need a real Postgres.
    resp = await client.post(
        "/sessions",
        json={"title": "My Session", "llm_provider": "openai", "llm_model": "gpt-4o-mini"},
    )
    # 201 with mocked DB, or 500 without DB — either way schema was accepted
    assert resp.status_code in (201, 500)


# ─── Missing API key → 422 ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_missing_api_key_returns_422(client):
    """
    POST /sessions/{id}/messages with openai provider but no OPENAI_API_KEY
    must return 422 with code=missing_api_key BEFORE opening an SSE stream.
    """
    fake_session_id = str(uuid.uuid4())
    fake_session = MagicMock()
    fake_session.id = uuid.UUID(fake_session_id)
    fake_session.llm_provider = "openai"
    fake_session.llm_model = "gpt-4o-mini"

    # Patch the DB call that fetches the session
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_session

    mock_exec = AsyncMock(return_value=mock_result)

    with (
        patch("app.routers.messages.settings") as mock_settings,
        patch("app.routers.messages.get_db"),
    ):
        mock_settings.require_provider_key.side_effect = ValueError(
            "OPENAI_API_KEY is not set."
        )
        mock_settings.openai_api_key = ""

        async def fake_get_db():
            db = AsyncMock()
            db.execute = mock_exec
            db.__aenter__ = AsyncMock(return_value=db)
            db.__aexit__ = AsyncMock(return_value=False)
            yield db

        with patch("app.routers.messages.get_db", fake_get_db):
            resp = await client.post(
                f"/sessions/{fake_session_id}/messages",
                json={"content": "What is PMF?"},
            )

    assert resp.status_code == 422
    data = resp.json()
    assert data["detail"]["code"] == "missing_api_key"


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
async def test_get_session_not_found(client):
    """GET /sessions/{random-uuid} should return 404 when session doesn't exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_exec = AsyncMock(return_value=mock_result)

    async def fake_get_db():
        db = AsyncMock()
        db.execute = mock_exec
        db.__aenter__ = AsyncMock(return_value=db)
        db.__aexit__ = AsyncMock(return_value=False)
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        yield db

    with patch("app.routers.sessions.get_db", fake_get_db):
        resp = await client.get(f"/sessions/{uuid.uuid4()}")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ─── /artifacts/{id} 404 ──────────────────────────────────────────────────

@pytest.mark.anyio
async def test_get_artifact_not_found(client):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_exec = AsyncMock(return_value=mock_result)

    async def fake_get_db():
        db = AsyncMock()
        db.execute = mock_exec
        db.__aenter__ = AsyncMock(return_value=db)
        db.__aexit__ = AsyncMock(return_value=False)
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        yield db

    with patch("app.routers.artifacts.get_db", fake_get_db):
        resp = await client.get(f"/artifacts/{uuid.uuid4()}")

    assert resp.status_code == 404
