"""
run_ingestion.py
~~~~~~~~~~~~~~~~
Orchestrate the full ingestion pipeline:

  1. Parse all transcripts  (parse_transcripts)
  2. Parse topic index      (parse_topic_index)
  3. Chunk each transcript   (chunker)
  4. Embed all chunks        (embed)
  5. Insert into Supabase    (SQLAlchemy, async)

Usage:
  # Dry-run on first 3 episodes (parse, chunk, embed — no DB writes):
  python -m app.ingestion.run_ingestion --dry-run --limit 3

  # Full ingestion:
  python -m app.ingestion.run_ingestion

  # Re-ingest, wiping existing data first:
  python -m app.ingestion.run_ingestion --reset
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import date
from pathlib import Path

import numpy as np

# ── Resolve paths ───────────────────────────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent
_DATASET_DIR = _PROJECT_ROOT / "dataset" / "lennys-podcast-transcripts-main"

# ── Local imports ───────────────────────────────────────────────
from app.ingestion.parse_transcripts import walk_episodes
from app.ingestion.parse_topic_index import parse_topic_index
from app.ingestion.chunker import chunk_transcript
from app.ingestion.embed import embed_texts

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────
# DB helpers (synchronous — ingestion is a one-off script)
# ────────────────────────────────────────────────────────────────

def _get_sync_engine():
    """Build a *synchronous* SQLAlchemy engine for the ingestion script.

    We convert the async connection string (postgresql+asyncpg://…) to
    a sync one (postgresql+psycopg2://…) since this is a batch script.
    """
    from app.config import settings
    import sqlalchemy as sa

    db_url = settings.supabase_db_url
    # Normalise to sync driver for the batch ingestion script.
    db_url = (
        db_url
        .replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        .replace("postgresql://", "postgresql+psycopg2://")
    )
    return sa.create_engine(db_url, echo=False)


def _insert_episode(conn, meta: dict, slug: str, topics: list[str]) -> str:
    """Insert a row into `episodes` and return its UUID (as str)."""
    import sqlalchemy as sa

    episode_id = str(uuid.uuid4())
    conn.execute(
        sa.text("""
            INSERT INTO episodes
                (id, guest, title, youtube_url, video_id, publish_date,
                 description, duration_seconds, view_count, topics)
            VALUES
                (:id, :guest, :title, :youtube_url, :video_id, :publish_date,
                 :description, :duration_seconds, :view_count, :topics)
        """),
        {
            "id": episode_id,
            "guest": meta["guest"],
            "title": meta["title"],
            "youtube_url": meta.get("youtube_url"),
            "video_id": meta.get("video_id"),
            "publish_date": meta.get("publish_date"),
            "description": meta.get("description"),
            "duration_seconds": meta.get("duration_seconds"),
            "view_count": meta.get("view_count"),
            "topics": topics,
        },
    )
    return episode_id


def _insert_chunks(conn, episode_id: str, chunks_data: list[dict]) -> None:
    """Batch-insert chunk rows for one episode."""
    import sqlalchemy as sa

    if not chunks_data:
        return
    conn.execute(
        sa.text("""
            INSERT INTO chunks (id, episode_id, content, chunk_index, embedding)
            VALUES (:id, :episode_id, :content, :chunk_index, :embedding)
        """),
        chunks_data,
    )


# ────────────────────────────────────────────────────────────────
# Main pipeline
# ────────────────────────────────────────────────────────────────

def run(
    dry_run: bool = False,
    limit: int | None = None,
    reset: bool = False,
) -> None:
    """Execute the full ingestion pipeline."""

    # 1. Parse transcripts ------------------------------------------------
    logger.info("=== Step 1/4: Parsing transcripts ===")
    episodes = walk_episodes(_DATASET_DIR)
    if limit:
        episodes = episodes[:limit]
        logger.info("  (limited to first %d episodes)", limit)
    total = len(episodes)

    # 2. Parse topic index ------------------------------------------------
    logger.info("=== Step 2/4: Parsing topic index ===")
    slug_to_topics = parse_topic_index(_DATASET_DIR)

    # 3. Chunk all transcripts -------------------------------------------
    logger.info("=== Step 3/4: Chunking transcripts ===")
    all_chunks_text: list[str] = []
    episode_chunk_map: list[tuple[int, int, int]] = []  # (ep_idx, start, end)

    for i, ep in enumerate(episodes):
        chunks = chunk_transcript(ep["body"])
        start = len(all_chunks_text)
        for c in chunks:
            all_chunks_text.append(c.text)
        end = len(all_chunks_text)
        episode_chunk_map.append((i, start, end))
        ep["_chunks"] = chunks  # stash for later
        logger.info(
            "  [%d/%d] %s — %d chunks",
            i + 1, total, ep["meta"]["guest"], len(chunks),
        )

    # 4. Embed all chunks at once ----------------------------------------
    logger.info("=== Step 4/4: Embedding %d chunks ===", len(all_chunks_text))
    if all_chunks_text:
        embeddings = embed_texts(all_chunks_text)
    else:
        embeddings = np.empty((0, 384), dtype=np.float32)

    # ── Summary ──────────────────────────────────────────────────
    logger.info(
        "Pipeline summary: %d episodes, %d total chunks, embedding shape %s",
        total,
        len(all_chunks_text),
        embeddings.shape,
    )

    if dry_run:
        logger.info("DRY RUN — skipping database writes.")
        # Print a quick preview.
        for ep_idx, start, end in episode_chunk_map:
            ep = episodes[ep_idx]
            topics = slug_to_topics.get(ep["slug"], [])
            logger.info(
                "  %-30s  chunks=%3d  topics=%s",
                ep["meta"]["guest"],
                end - start,
                topics[:5],
            )
            # Show first chunk preview.
            if start < end:
                preview = all_chunks_text[start][:200].replace("\n", " ")
                logger.info("    chunk[0] preview: %s…", preview)
        return

    # 5. Write to DB ─────────────────────────────────────────────
    engine = _get_sync_engine()
    with engine.begin() as conn:
        if reset:
            logger.warning("RESET: deleting all existing episodes and chunks.")
            import sqlalchemy as sa
            conn.execute(sa.text("DELETE FROM chunks"))
            conn.execute(sa.text("DELETE FROM episodes"))

        for ep_idx, start, end in episode_chunk_map:
            ep = episodes[ep_idx]
            topics = slug_to_topics.get(ep["slug"], [])
            try:
                episode_id = _insert_episode(conn, ep["meta"], ep["slug"], topics)
                chunk_rows = []
                for j in range(start, end):
                    chunk_rows.append(
                        {
                            "id": str(uuid.uuid4()),
                            "episode_id": episode_id,
                            "content": all_chunks_text[j],
                            "chunk_index": j - start,
                            "embedding": embeddings[j].tolist().__str__(),
                            # pgvector accepts '[0.1, 0.2, ...]' string format
                        }
                    )
                _insert_chunks(conn, episode_id, chunk_rows)
                logger.info(
                    "  [%d/%d] ✓ %s — %d chunks inserted",
                    ep_idx + 1, total, ep["meta"]["guest"], len(chunk_rows),
                )
            except Exception:
                logger.exception(
                    "  [%d/%d] ✗ FAILED: %s — skipping",
                    ep_idx + 1, total, ep["meta"]["guest"],
                )

    logger.info("=== Ingestion complete ===")


# ────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Lenny Growth Assistant — Data Ingestion")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse, chunk, and embed but skip DB writes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N episodes (for testing).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing episodes/chunks before inserting.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    run(dry_run=args.dry_run, limit=args.limit, reset=args.reset)


if __name__ == "__main__":
    main()
