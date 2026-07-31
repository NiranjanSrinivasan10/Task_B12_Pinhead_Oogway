-- 001_init.sql
-- Schema for The Lenny Growth Assistant
-- Run this in the Supabase SQL Editor (or any Postgres 15+ with pgvector).

-- ============================================================
-- 0. Extensions
-- ============================================================
CREATE EXTENSION IF NOT EXISTS vector;        -- pgvector
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- uuid_generate_v4()

-- ============================================================
-- 1. episodes
-- ============================================================
CREATE TABLE episodes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    guest           TEXT        NOT NULL,
    title           TEXT        NOT NULL,
    youtube_url     TEXT,
    video_id        TEXT,
    publish_date    DATE,
    description     TEXT,
    duration_seconds FLOAT,
    view_count      INTEGER,
    topics          TEXT[]      DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 2. chunks  (384-dim embeddings — all-MiniLM-L6-v2)
-- ============================================================
CREATE TABLE chunks (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    episode_id  UUID        NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    content     TEXT        NOT NULL,
    chunk_index INTEGER     NOT NULL,
    embedding   vector(384),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- IVFFlat index for cosine similarity search
-- NOTE: IVFFlat requires the table to have data before building the index.
--       After the initial data ingestion, run:
--         CREATE INDEX idx_chunks_embedding ON chunks
--           USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
--       The number of lists should be ~ sqrt(row_count). 100 is a safe
--       starting point for the ~303-episode corpus.
--       Alternatively, use HNSW (no data requirement):
CREATE INDEX idx_chunks_embedding ON chunks
    USING hnsw (embedding vector_cosine_ops);

-- Fast lookup of chunks by episode
CREATE INDEX idx_chunks_episode_id ON chunks(episode_id);

-- ============================================================
-- 3. sessions
-- ============================================================
CREATE TABLE sessions (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title        TEXT        NOT NULL DEFAULT 'New Chat',
    llm_provider TEXT        NOT NULL DEFAULT 'openai',
    llm_model    TEXT        NOT NULL DEFAULT 'gpt-4o-mini',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 4. messages
-- ============================================================
CREATE TABLE messages (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id          UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role                TEXT        NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content             TEXT        NOT NULL,
    skill_used          TEXT,
    retrieved_chunk_ids UUID[]      DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_messages_session_id ON messages(session_id);

-- ============================================================
-- 5. artifacts
-- ============================================================
CREATE TABLE artifacts (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID        NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    session_id UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    type       TEXT        NOT NULL CHECK (type IN ('markdown', 'html')),
    title      TEXT        NOT NULL,
    content    TEXT        NOT NULL,
    version    INTEGER     NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_artifacts_session_id ON artifacts(session_id);
CREATE INDEX idx_artifacts_message_id ON artifacts(message_id);
