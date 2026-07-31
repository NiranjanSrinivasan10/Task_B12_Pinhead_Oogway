"""
routers/sessions.py
~~~~~~~~~~~~~~~~~~~
CRUD endpoints for chat sessions.

  POST   /sessions          — create a new session
  GET    /sessions          — list all sessions (sidebar)
  GET    /sessions/{id}     — get session with full message history
  PATCH  /sessions/{id}/config — update llm_provider / llm_model / title
"""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import Session as SessionModel, Message as MessageModel
from ..schemas import (
    SessionCreate,
    SessionConfigPatch,
    SessionListItem,
    SessionOut,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=SessionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
)
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    session = SessionModel(
        title=body.title,
        llm_provider=body.llm_provider,
        llm_model=body.llm_model,
    )
    db.add(session)
    await db.flush()  # generate PK without committing
    await db.refresh(session)
    return SessionOut.model_validate(session)


@router.get(
    "",
    response_model=List[SessionListItem],
    summary="List all sessions (sidebar)",
)
async def list_sessions(
    db: AsyncSession = Depends(get_db),
) -> List[SessionListItem]:
    result = await db.execute(
        select(SessionModel).order_by(SessionModel.updated_at.desc())
    )
    sessions = result.scalars().all()
    return [SessionListItem.model_validate(s) for s in sessions]


@router.get(
    "/{session_id}",
    response_model=SessionOut,
    summary="Get session with full message history",
)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    result = await db.execute(
        select(SessionModel)
        .where(SessionModel.id == session_id)
        .options(selectinload(SessionModel.messages))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found.",
        )
    return SessionOut.model_validate(session)


@router.patch(
    "/{session_id}/config",
    response_model=SessionOut,
    summary="Update llm_provider / llm_model / title for a session",
)
async def patch_session_config(
    session_id: uuid.UUID,
    body: SessionConfigPatch,
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    result = await db.execute(
        select(SessionModel)
        .where(SessionModel.id == session_id)
        .options(selectinload(SessionModel.messages))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found.",
        )

    updates = body.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(session, field, value)

    # Explicitly bump updated_at (server_default doesn't fire on UPDATE via ORM)
    from sqlalchemy import func
    session.updated_at = func.now()

    await db.flush()
    await db.refresh(session)
    return SessionOut.model_validate(session)
