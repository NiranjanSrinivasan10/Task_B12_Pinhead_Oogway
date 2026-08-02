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
from ..models import Session as SessionModel, Message as MessageModel, Artifact as ArtifactModel
from ..schemas import (
    SessionCreate,
    SessionConfigPatch,
    SessionTitlePatch,
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
    # Explicitly construct with messages=[] and artifacts=[] — a brand-new session
    # always has zero messages and zero artifacts, and accessing the lazy-loaded ORM
    # relationships here would trigger MissingGreenlet (async lazy-load inside
    # Pydantic's sync validator).
    return SessionOut(
        id=session.id,
        title=session.title,
        llm_provider=session.llm_provider,
        llm_model=session.llm_model,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[],
        artifacts=[],
    )


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
    summary="Get session with full message history and artifacts",
)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    result = await db.execute(
        select(SessionModel)
        .where(SessionModel.id == session_id)
        .options(selectinload(SessionModel.messages))
        .options(selectinload(SessionModel.artifacts))
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
    summary="Update llm_provider / llm_model for a session",
)
async def patch_session_config(
    session_id: uuid.UUID,
    body: SessionConfigPatch,
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
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

    # Re-query with selectinload to eagerly fetch messages and artifacts for
    # SessionOut serialization — db.refresh() does NOT reload relationships.
    refreshed = await db.execute(
        select(SessionModel)
        .where(SessionModel.id == session_id)
        .options(selectinload(SessionModel.messages))
        .options(selectinload(SessionModel.artifacts))
    )
    session = refreshed.scalar_one()
    return SessionOut.model_validate(session)


@router.patch(
    "/{session_id}",
    response_model=SessionListItem,
    summary="Update session title",
)
async def patch_session_title(
    session_id: uuid.UUID,
    body: SessionTitlePatch,
    db: AsyncSession = Depends(get_db),
) -> SessionListItem:
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found.",
        )

    session.title = body.title

    # Explicitly bump updated_at
    from sqlalchemy import func
    session.updated_at = func.now()

    await db.commit()
    await db.refresh(session)

    return SessionListItem.model_validate(session)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a session (cascades to messages and artifacts)",
)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found.",
        )

    await db.delete(session)
    await db.commit()
