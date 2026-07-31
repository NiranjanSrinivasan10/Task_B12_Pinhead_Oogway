"""
embed.py
~~~~~~~~
Embed text chunks using sentence-transformers ``all-MiniLM-L6-v2``.

┌────────────────────────────────────────────────────────────────────┐
│ ARCHITECTURE DECISION — Embedding model is DECOUPLED from the     │
│ chat LLM toggle (see ARCHITECTURE.md §2 "Embedding model").       │
│                                                                   │
│ This SAME local model (all-MiniLM-L6-v2, 384 dims) is used for   │
│ BOTH ingestion-time embedding AND query-time embedding, regardless│
│ of whether the active chat LLM is OpenAI (cloud) or Ollama        │
│ (local). Reasons:                                                 │
│                                                                   │
│ 1. Local demo stays fully local — zero cloud API calls for search │
│    even in "local" mode; no OPENAI_API_KEY needed for retrieval.  │
│ 2. Vector-space consistency — ingestion and query embeddings are   │
│    always in the same 384-dim space; mixing models would silently  │
│    degrade cosine similarity with no visible error.               │
│ 3. One fewer dependency/cost — no OpenAI Embeddings API usage.    │
│                                                                   │
│ Tradeoff accepted: MiniLM's 384-dim embeddings have lower         │
│ fidelity than OpenAI's 1536-dim embeddings, but the hybrid router │
│ (topic-tag pre-filter + vector search) compensates by narrowing   │
│ candidates before vector similarity is evaluated.                 │
│                                                                   │
│ Output dimension: 384 — must match chunks.embedding column type   │
│ (vector(384)) in the DB schema.                                   │
└────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Lazy-loaded singleton so the model isn't imported at module level
# (avoids a multi-second delay for scripts that don't need it).
_model = None
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_EXPECTED_DIM = 384


def _get_model():
    """Load the SentenceTransformer model (once)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s", _MODEL_NAME)
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed_texts(texts: list[str], batch_size: int = 64) -> NDArray[np.float32]:
    """Embed a list of texts into 384-dim float32 vectors.

    Args:
        texts: The strings to embed.
        batch_size: Encoding batch size (tune for GPU/CPU memory).

    Returns:
        numpy array of shape (len(texts), 384).
    """
    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=len(texts) > 100,
        convert_to_numpy=True,
        normalize_embeddings=True,  # unit vectors → cosine = dot product
    )
    assert embeddings.shape[1] == _EXPECTED_DIM, (
        f"Expected {_EXPECTED_DIM}-dim embeddings, got {embeddings.shape[1]}"
    )
    logger.info("Embedded %d texts → shape %s", len(texts), embeddings.shape)
    return embeddings


def embed_query(query: str) -> NDArray[np.float32]:
    """Embed a single query string (convenience wrapper for search).

    Returns a 1-D array of shape (384,).
    """
    return embed_texts([query])[0]
