"""
routers/health.py
~~~~~~~~~~~~~~~~~
GET /health — checks DB connectivity, Ollama reachability, Pi subprocess status.

Returns HTTP 200 with status "ok" if all checks pass.
Returns HTTP 200 with status "degraded" if some checks fail (degraded, not down).
Never returns 5xx from this endpoint so load-balancers / uptime monitors can
distinguish "app is up but degraded" from "app is truly down".
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..config import settings
from ..database import check_db_connection
from ..pi_client import pi_client
from ..schemas import HealthStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


async def _check_ollama() -> tuple[bool, str]:
    """Ping the Ollama /api/tags endpoint; return (ok, detail)."""
    url = settings.ollama_base_url.rstrip("/") + "/api/tags"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return True, "reachable"
            return False, f"HTTP {resp.status_code}"
    except httpx.ConnectError:
        return False, "connection refused"
    except httpx.TimeoutException:
        return False, "timeout"
    except Exception as exc:
        return False, str(exc)


def _check_pi() -> tuple[bool, str]:
    """Check whether the Pi subprocess is alive (non-blocking)."""
    proc = pi_client._proc
    if proc is None:
        return False, "not started"
    if proc.returncode is not None:
        return False, f"exited with code {proc.returncode}"
    return True, "running"


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="Health check: DB, Ollama, Pi subprocess",
)
async def health_check() -> JSONResponse:
    db_ok = await check_db_connection()
    ollama_ok, ollama_detail = await _check_ollama()
    pi_ok, pi_detail = _check_pi()

    all_ok = db_ok  # Ollama + Pi are optional services
    degraded = not all_ok or not ollama_ok or not pi_ok

    if db_ok and ollama_ok and pi_ok:
        overall = "ok"
        http_status = 200
    elif not db_ok:
        overall = "unhealthy"
        http_status = 200  # still 200 so monitors can read the payload
    else:
        overall = "degraded"
        http_status = 200

    payload = HealthStatus(
        status=overall,
        db=db_ok,
        ollama=ollama_ok,
        pi_subprocess=pi_ok,
        details={
            "ollama": ollama_detail,
            "pi": pi_detail,
            "ollama_base_url": settings.ollama_base_url,
        },
    )
    return JSONResponse(status_code=http_status, content=payload.model_dump())
