"""
routers/artifacts.py
~~~~~~~~~~~~~~~~~~~~
GET /artifacts/{id} — fetch a specific artifact.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Artifact as ArtifactModel
from ..schemas import ArtifactOut

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get(
    "/{artifact_id}",
    response_model=ArtifactOut,
    summary="Fetch a specific artifact by ID",
)
async def get_artifact(
    artifact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ArtifactOut:
    result = await db.execute(
        select(ArtifactModel).where(ArtifactModel.id == artifact_id)
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_id} not found.",
        )
    return ArtifactOut.model_validate(artifact)
