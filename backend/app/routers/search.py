"""
routers/search.py
~~~~~~~~~~~~~~~~~
Hybrid retrieval implementation used by the messages router.

Algorithm:
  1. Topic-tag pre-filter: match query keywords against episodes.topics to
     narrow the candidate episode set (zero embedding calls).
  2. pgvector cosine similarity on chunks WHERE episode_id IN (candidates),
     top-K results.
  3. Fallback: if candidates is empty OR top score < threshold, re-run
     vector search across the full corpus.

The embedding model is always all-MiniLM-L6-v2 (384-dim), decoupled from
whatever chat LLM is selected.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session_factory
from ..models import Chunk, Episode

logger = logging.getLogger(__name__)

# Lazy-load the embedding model on first use (heavy import)
_embed_fn = None


def _get_embed_fn():
    global _embed_fn
    if _embed_fn is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        _embed_fn = lambda text: _model.encode(text, convert_to_numpy=True).tolist()
    return _embed_fn


RELEVANCE_THRESHOLD = 0.30  # cosine similarity cutoff for fallback trigger


async def _embed_query(query: str) -> list[float]:
    """Embed the query string synchronously (SentenceTransformer is not async)."""
    import asyncio
    loop = asyncio.get_event_loop()
    fn = _get_embed_fn()
    # Run in executor to avoid blocking the event loop
    embedding = await loop.run_in_executor(None, fn, query)
    return embedding


async def _topic_candidates(query: str, db: AsyncSession) -> list[uuid.UUID]:
    """
    Return episode IDs whose topics overlap with query keywords.
    Cheap text match — no embedding call.
    """
    words = set(query.lower().split())
    # Fetch all episodes with their topics (small table, fine to load all)
    result = await db.execute(select(Episode.id, Episode.topics))
    rows = result.all()

    candidates = []
    for episode_id, topics in rows:
        if not topics:
            continue
        for topic in topics:
            topic_words = set(topic.lower().replace("-", " ").split())
            if words & topic_words:
                candidates.append(episode_id)
                break
    return candidates


async def _vector_search(
    embedding: list[float],
    db: AsyncSession,
    episode_ids: list[uuid.UUID] | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Run pgvector cosine similarity search.
    If episode_ids is provided, restrict to those episodes.
    """
    vec_literal = "[" + ",".join(str(v) for v in embedding) + "]"

    if episode_ids:
        id_list = ",".join(f"'{eid}'" for eid in episode_ids)
        sql = text(f"""
            SELECT
                c.id          AS chunk_id,
                c.content     AS content,
                c.chunk_index AS chunk_index,
                e.guest       AS guest,
                e.title       AS title,
                e.id          AS episode_id,
                1 - (c.embedding <=> '{vec_literal}'::vector) AS score
            FROM chunks c
            JOIN episodes e ON e.id = c.episode_id
            WHERE c.episode_id IN ({id_list})
            ORDER BY c.embedding <=> '{vec_literal}'::vector
            LIMIT :top_k
        """)
    else:
        sql = text(f"""
            SELECT
                c.id          AS chunk_id,
                c.content     AS content,
                c.chunk_index AS chunk_index,
                e.guest       AS guest,
                e.title       AS title,
                e.id          AS episode_id,
                1 - (c.embedding <=> '{vec_literal}'::vector) AS score
            FROM chunks c
            JOIN episodes e ON e.id = c.episode_id
            ORDER BY c.embedding <=> '{vec_literal}'::vector
            LIMIT :top_k
        """)

    result = await db.execute(sql, {"top_k": top_k})
    rows = result.mappings().all()
    return [dict(r) for r in rows]


async def hybrid_search(
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Full hybrid retrieval pipeline.

    Returns a list of dicts with keys:
      chunk_id, content, chunk_index, guest, title, episode_id, score
    """
    db_factory = get_session_factory()
    async with db_factory() as db:
        # Step 1: topic-tag pre-filter
        candidates = await _topic_candidates(query, db)
        logger.debug("Topic-filter candidates: %d episodes", len(candidates))

        # Step 2: embed query
        try:
            embedding = await _embed_query(query)
        except Exception as exc:
            logger.error("Embedding failed: %s", exc)
            return []

        # Step 3: vector search on candidates
        results = []
        if candidates:
            results = await _vector_search(embedding, db, episode_ids=candidates, top_k=top_k)

        # Step 4: fallback if no candidates or low scores
        if not results or (results and results[0].get("score", 0) < RELEVANCE_THRESHOLD):
            logger.debug("Falling back to full-corpus vector search")
            results = await _vector_search(embedding, db, episode_ids=None, top_k=top_k)

        return results
