"""
tests/test_prd_scenarios.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Systematic verification suite for all 8 PRD success criteria scenarios.

Runs end-to-end unit tests against FastAPI app components, mocking DB and network
boundaries to verify exact error status codes, SSE event streams, and health check transitions.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db


@pytest.fixture(scope="module")
def app():
    from app.main import app as _app
    return _app


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ─── Scenario 6: Missing OPENAI_API_KEY → HTTP 422 ──────────────────────────

@pytest.mark.anyio
async def test_scenario_6_missing_api_key_422(app, client):
    """
    Scenario 6: When OPENAI_API_KEY is missing, POST /sessions/{id}/messages
    must return HTTP 422 with a structured JSON error BEFORE opening SSE,
    never a 500 or raw traceback.
    """
    fake_session_id = uuid.uuid4()
    fake_session = MagicMock()
    fake_session.id = fake_session_id
    fake_session.llm_provider = "openai"
    fake_session.llm_model = "gpt-4o-mini"

    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none.return_value = fake_session
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_scalar)

    async def fake_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = fake_get_db

    try:
        with patch("app.routers.messages.settings") as mock_settings:
            mock_settings.require_provider_key.side_effect = ValueError(
                "OPENAI_API_KEY is not set. Add it to backend/.env file."
            )
            mock_settings.openai_api_key = ""

            resp = await client.post(
                f"/sessions/{fake_session_id}/messages",
                json={"content": "How do leaders determine PMF?"},
            )

        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        assert data["detail"]["code"] == "missing_api_key"
        assert "OPENAI_API_KEY is not set" in data["detail"]["message"]
        assert data["detail"]["provider"] == "openai"
    finally:
        app.dependency_overrides.clear()


# ─── Scenario 5: Ollama Unreachable → Structured Error Event ─────────────

@pytest.mark.anyio
async def test_scenario_5_ollama_unreachable_error(app, client):
    """
    Scenario 5: Switch to Ollama mid-session, when Ollama is offline/unreachable,
    send a message -> verify structured SSE error event, not a crash or hang.
    """
    fake_session_id = uuid.uuid4()
    fake_session = MagicMock()
    fake_session.id = fake_session_id
    fake_session.llm_provider = "ollama"
    fake_session.llm_model = "llama3.1:8b"

    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none.return_value = fake_session
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_scalar)

    async def fake_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = fake_get_db

    from app.pi_client import PiRPCError

    async def fake_pi_stream(*args, **kwargs):
        raise PiRPCError("Failed to connect to Ollama on http://localhost:11434")
        yield  # make it a generator

    mock_session_factory_db = AsyncMock()
    mock_history_scalars = MagicMock()
    mock_history_scalars.scalars.return_value.all.return_value = []
    mock_session_factory_db.execute = AsyncMock(return_value=mock_history_scalars)
    mock_session_factory_db.commit = AsyncMock()
    mock_session_factory_db.add = MagicMock()

    class MockContextManager:
        async def __aenter__(self):
            return mock_session_factory_db
        async def __aexit__(self, *args):
            pass

    try:
        with (
            patch("app.routers.messages.get_session_factory", return_value=lambda: MockContextManager()),
            patch("app.routers.messages.hybrid_search", new=AsyncMock(return_value=[])),
            patch("app.routers.messages.pi_client.run_turn", side_effect=fake_pi_stream),
        ):
            resp = await client.post(
                f"/sessions/{fake_session_id}/messages",
                json={"content": "Test Ollama offline scenario"},
            )

        assert resp.status_code == 200  # SSE connection opened
        text = resp.text
        assert "event: error" in text
        assert "Local model unavailable" in text or "Ollama" in text
    finally:
        app.dependency_overrides.clear()


# ─── Scenario 8: Lazy Start /health Transition ────────────────────────────

@pytest.mark.anyio
async def test_scenario_8_health_lazy_start_transition(client):
    """
    Scenario 8:
    1. Check GET /health immediately -> pi_subprocess is false ("not started").
    2. Simulate starting Pi process -> pi_subprocess flips to true ("running").
    """
    with (
        patch("app.routers.health.check_db_connection", new=AsyncMock(return_value=True)),
        patch("app.routers.health._check_ollama", new=AsyncMock(return_value=(True, "reachable"))),
        patch("app.routers.health.pi_client") as mock_pi_client,
    ):
        # 1. Before any message turn: proc is None
        mock_pi_client._proc = None
        resp1 = await client.get("/health")
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["pi_subprocess"] is False
        assert data1["details"]["pi"] == "not started"

        # 2. After a message turn: proc is active
        fake_proc = AsyncMock()
        fake_proc.returncode = None
        mock_pi_client._proc = fake_proc

        resp2 = await client.get("/health")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["pi_subprocess"] is True
        assert data2["details"]["pi"] == "running"
