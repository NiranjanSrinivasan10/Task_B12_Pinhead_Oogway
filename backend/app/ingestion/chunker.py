"""
chunker.py
~~~~~~~~~~
Split transcript bodies into overlapping chunks of ~500-800 tokens,
preserving paragraph boundaries where possible.

Uses tiktoken (cl100k_base encoding) for accurate token counting.

Strategy:
  1. Split on double-newlines to get paragraph-level blocks.
  2. Greedily accumulate paragraphs until adding the next would exceed
     MAX_TOKENS.  Emit the accumulated text as a chunk.
  3. Roll back by OVERLAP_TOKENS worth of trailing paragraphs to start
     the next chunk — this gives contextual overlap at paragraph
     boundaries rather than mid-sentence.
  4. If a single paragraph exceeds MAX_TOKENS on its own, hard-split it
     by token count (unavoidable for very long paragraphs).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import tiktoken

logger = logging.getLogger(__name__)

# ── Tunables ────────────────────────────────────────────────────
MAX_TOKENS = 700       # target ceiling per chunk
MIN_TOKENS = 300       # avoid emitting very short chunks
OVERLAP_TOKENS = 100   # overlap between consecutive chunks
# ────────────────────────────────────────────────────────────────

_enc = tiktoken.get_encoding("cl100k_base")


def _token_len(text: str) -> int:
    return len(_enc.encode(text))


@dataclass
class Chunk:
    """A single chunk of transcript text."""
    text: str
    index: int          # 0-based position within the episode
    token_count: int


def _hard_split(text: str, max_tokens: int) -> list[str]:
    """Split a single oversized paragraph into token-bounded pieces."""
    tokens = _enc.encode(text)
    pieces: list[str] = []
    for i in range(0, len(tokens), max_tokens):
        pieces.append(_enc.decode(tokens[i : i + max_tokens]))
    return pieces


def chunk_transcript(body: str) -> list[Chunk]:
    """Split *body* into overlapping chunks.

    Returns a list of Chunk objects ordered by index.
    """
    # 1. Split into paragraph-level blocks.
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

    # Expand any single paragraph that exceeds MAX_TOKENS.
    blocks: list[str] = []
    for para in paragraphs:
        if _token_len(para) > MAX_TOKENS:
            blocks.extend(_hard_split(para, MAX_TOKENS))
        else:
            blocks.append(para)

    if not blocks:
        return []

    chunks: list[Chunk] = []
    idx = 0           # current position in blocks
    chunk_index = 0

    while idx < len(blocks):
        current_parts: list[str] = []
        current_tokens = 0

        # Greedily accumulate blocks.
        while idx < len(blocks):
            block_tokens = _token_len(blocks[idx])
            if current_tokens + block_tokens > MAX_TOKENS and current_parts:
                break
            current_parts.append(blocks[idx])
            current_tokens += block_tokens
            idx += 1

        text = "\n\n".join(current_parts)
        chunks.append(Chunk(text=text, index=chunk_index, token_count=_token_len(text)))
        chunk_index += 1

        # Roll back for overlap: walk backwards until we've accumulated
        # at least OVERLAP_TOKENS of trailing context.
        if idx < len(blocks):
            overlap_tokens = 0
            rollback = 0
            for j in range(len(current_parts) - 1, -1, -1):
                overlap_tokens += _token_len(current_parts[j])
                rollback += 1
                if overlap_tokens >= OVERLAP_TOKENS:
                    break
            idx -= rollback

    logger.debug(
        "Chunked transcript into %d chunks (avg %d tokens)",
        len(chunks),
        sum(c.token_count for c in chunks) // max(len(chunks), 1),
    )
    return chunks
