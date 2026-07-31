"""
backend.app.schemas
~~~~~~~~~~~~~~~~~~~
Pydantic request / response models for all API endpoints.

Kept as pure Pydantic (no ORM coupling) so they can be validated and
serialized independently of the DB layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────
# Sessions
# ─────────────────────────────────────────────

class SessionCreate(BaseModel):
    title: str = Field(default="New Chat", max_length=200)
    llm_provider: Literal["openai", "anthropic", "ollama"] = "openai"
    llm_model: str = Field(default="gpt-4o-mini", max_length=100)


class SessionConfigPatch(BaseModel):
    llm_provider: Optional[Literal["openai", "anthropic", "ollama"]] = None
    llm_model: Optional[str] = Field(default=None, max_length=100)
    title: Optional[str] = Field(default=None, max_length=200)


class MessageOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    skill_used: Optional[str]
    retrieved_chunk_ids: List[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class ArtifactOut(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    session_id: uuid.UUID
    type: str
    title: str
    content: str
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: uuid.UUID
    title: str
    llm_provider: str
    llm_model: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageOut] = []

    model_config = {"from_attributes": True}


class SessionListItem(BaseModel):
    id: uuid.UUID
    title: str
    llm_provider: str
    llm_model: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# Messages (POST /sessions/{id}/messages)
# ─────────────────────────────────────────────

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=32_000)


# ─────────────────────────────────────────────
# SSE event payloads
# ─────────────────────────────────────────────

class SSEMessageDelta(BaseModel):
    type: Literal["message_delta"] = "message_delta"
    content: str


class SSEArtifactCreated(BaseModel):
    type: Literal["artifact_created"] = "artifact_created"
    id: str
    artifact_type: str
    title: str
    content: str


class SSEError(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str


class SSEDone(BaseModel):
    type: Literal["done"] = "done"
    message_id: str
    skill_used: Optional[str] = None


# ─────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────

class HealthStatus(BaseModel):
    status: Literal["ok", "degraded", "unhealthy"]
    db: bool
    ollama: bool
    pi_subprocess: bool
    details: Dict[str, Any] = {}
