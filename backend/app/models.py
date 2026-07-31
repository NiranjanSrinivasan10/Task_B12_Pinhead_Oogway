"""
backend.app.models
~~~~~~~~~~~~~~~~~~
SQLAlchemy ORM models matching the schema in migrations/001_init.sql.

All tables use UUID primary keys (server-side default via gen_random_uuid()).
The `pgvector` extension is handled in the migration; for ORM purposes, the
embedding column is typed as ARRAY(Float) — we insert/query it as a Python
list[float] and let asyncpg/pgvector do the casting.
"""

from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    guest: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    youtube_url: Mapped[Optional[str]] = mapped_column(Text)
    video_id: Mapped[Optional[str]] = mapped_column(Text)
    publish_date: Mapped[Optional[date]] = mapped_column(Date)
    description: Mapped[Optional[str]] = mapped_column(Text)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    view_count: Mapped[Optional[int]] = mapped_column(Integer)
    topics: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk", back_populates="episode", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    episode_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Store embedding as a list; the DB column is vector(384) from pgvector
    embedding: Mapped[Optional[List[float]]] = mapped_column(ARRAY(Float))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    episode: Mapped["Episode"] = relationship("Episode", back_populates="chunks")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(Text, nullable=False, default="New Chat")
    llm_provider: Mapped[str] = mapped_column(Text, nullable=False, default="openai")
    llm_model: Mapped[str] = mapped_column(Text, nullable=False, default="gpt-4o-mini")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan",
        order_by="Message.created_at"
    )
    artifacts: Mapped[List["Artifact"]] = relationship(
        "Artifact", back_populates="session", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        Text, nullable=False,
        # Valid values enforced at DB level too; Pydantic validates at API level
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    skill_used: Mapped[Optional[str]] = mapped_column(Text)
    retrieved_chunk_ids: Mapped[List[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="messages")
    artifacts: Mapped[List["Artifact"]] = relationship(
        "Artifact", back_populates="message", cascade="all, delete-orphan"
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)   # 'markdown' | 'html'
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="artifacts")
    session: Mapped["Session"] = relationship("Session", back_populates="artifacts")
