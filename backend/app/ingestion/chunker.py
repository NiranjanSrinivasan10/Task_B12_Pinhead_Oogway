"""
chunker.py
~~~~~~~~~~
Split transcript bodies into overlapping chunks of ~500-800 tokens,
preserving paragraph and sentence boundaries where possible.

Uses tiktoken (cl100k_base encoding) for accurate token counting.

Strategy:
  1. Split on double-newlines to get paragraph-level blocks.
  2. If a single paragraph exceeds MAX_TOKENS, split it into sentences and
     greedily group sentences up to MAX_TOKENS per block.
  3. If a single sentence exceeds MAX_TOKENS on its own, hard-split it
     by token count (unavoidable for extremely long single sentences).
  4. Greedily accumulate blocks until adding the next would exceed
     MAX_TOKENS. Emit the accumulated text as a chunk.
  5. Roll back by OVERLAP_TOKENS worth of trailing blocks to start
     the next chunk — this gives contextual overlap at sentence/paragraph
     boundaries rather than mid-sentence.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import tiktoken

logger = logging.getLogger(__name__)

# ── Tunables ────────────────────────────────────────────────────
MAX_TOKENS = 700       # target ceiling per chunk
MIN_TOKENS = 300       # avoid emitting very short chunks (NOTE: currently unused in chunk_transcript)
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
    """Split a single oversized element into token-bounded pieces."""
    tokens = _enc.encode(text)
    pieces: list[str] = []
    for i in range(0, len(tokens), max_tokens):
        pieces.append(_enc.decode(tokens[i : i + max_tokens]))
    return pieces


def _split_by_sentence(text: str) -> list[str]:
    """Split text into sentences using punctuation lookbehind regex."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_transcript(body: str) -> list[Chunk]:
    """Split *body* into overlapping chunks using paragraph -> sentence -> token hierarchy.

    Returns a list of Chunk objects ordered by index.
    """
    # 1. Split into paragraph-level blocks.
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

    # Expand any single paragraph that exceeds MAX_TOKENS via sentence-level splitting.
    blocks: list[str] = []
    for para in paragraphs:
        if _token_len(para) > MAX_TOKENS:
            sentences = _split_by_sentence(para)
            curr_sent_group: list[str] = []
            curr_sent_tokens = 0

            for sent in sentences:
                sent_len = _token_len(sent)
                if sent_len > MAX_TOKENS:
                    # Flush accumulated sentence group first
                    if curr_sent_group:
                        blocks.append(" ".join(curr_sent_group))
                        curr_sent_group = []
                        curr_sent_tokens = 0
                    # Single sentence exceeds MAX_TOKENS -> fallback to hard split
                    blocks.extend(_hard_split(sent, MAX_TOKENS))
                else:
                    if curr_sent_tokens + sent_len > MAX_TOKENS and curr_sent_group:
                        blocks.append(" ".join(curr_sent_group))
                        curr_sent_group = [sent]
                        curr_sent_tokens = sent_len
                    else:
                        curr_sent_group.append(sent)
                        curr_sent_tokens += sent_len

            if curr_sent_group:
                blocks.append(" ".join(curr_sent_group))
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
            rollback = min(rollback, len(current_parts) - 1)
            idx -= rollback

    logger.debug(
        "Chunked transcript into %d chunks (avg %d tokens)",
        len(chunks),
        sum(c.token_count for c in chunks) // max(len(chunks), 1),
    )
    return chunks
