"""
backend.app.main
~~~~~~~~~~~~~~~~
FastAPI application entry point.

Start the server:
    cd backend
    .\\venv\\Scripts\\activate   (Windows)
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .pi_client import pi_client
from .routers import artifacts, health, messages, sessions

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Lenny Growth Assistant API",
    description=(
        "RAG-powered chat assistant grounded in Lenny's Podcast transcripts. "
        "Supports cloud (OpenAI) and local (Ollama) LLMs."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Allow the Vite dev server on port 5173 and production builds.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(sessions.router)
app.include_router(messages.router)
app.include_router(artifacts.router)
app.include_router(health.router)

# ─── Lifespan ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def _startup() -> None:
    """Validate DB connection at startup; fail loudly if the DB is unreachable."""
    logger.info("=== Lenny Growth Assistant API starting up ===")

    # 1. Check DB connection
    from .database import check_db_connection
    db_ok = await check_db_connection()
    if db_ok:
        logger.info("[OK] Database connection OK")
    else:
        logger.error(
            "[FAIL] Database connection FAILED. "
            "Check SUPABASE_DB_URL in backend/.env. "
            "The /health endpoint will report 'unhealthy'."
        )
        # We intentionally do NOT abort startup -- the app stays up so that
        # /health can be queried and the operator sees a clear status message.

    # 2. Log active LLM provider availability
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set -- OpenAI provider will fail at request time.")
    else:
        logger.info("[OK] OPENAI_API_KEY present")

    if not settings.anthropic_api_key:
        logger.info("ANTHROPIC_API_KEY not set (optional for this submission).")


@app.on_event("shutdown")
async def _shutdown() -> None:
    """Gracefully shut down the Pi subprocess."""
    logger.info("Shutting down Pi RPC subprocess...")
    await pi_client.close()
    logger.info("=== Lenny Growth Assistant API shut down ===")


# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["root"], include_in_schema=False)
async def root():
    return {
        "name": "Lenny Growth Assistant API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
