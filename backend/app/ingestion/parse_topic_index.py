"""
parse_topic_index.py
~~~~~~~~~~~~~~~~~~~~
Parse the AI-generated topic index files in dataset/index/*.md and
build a mapping of episode-slug → list[topic-tag].

Each topic file (e.g. index/growth-strategy.md) has the format:

    # growth strategy

    Episodes discussing **growth strategy**:

    - [Guest Name](../episodes/guest-slug/transcript.md)
    - [Another Guest](../episodes/another-slug/transcript.md)

We extract the slug from each bullet's relative link and associate it
with the topic derived from the filename (growth-strategy → "growth strategy").
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

# Matches: - [Display Name](../episodes/<slug>/transcript.md)
_LINK_RE = re.compile(
    r"^\s*-\s*\[.*?\]\(\.\./episodes/([^/]+)/transcript\.md\)",
    re.MULTILINE,
)


def _topic_from_filename(filename: str) -> str:
    """Convert a filename like 'growth-strategy.md' → 'growth strategy'."""
    return filename.removesuffix(".md").replace("-", " ")


def parse_topic_index(dataset_dir: Path) -> dict[str, list[str]]:
    """Build a slug → [topic, ...] mapping from dataset/index/*.md.

    Skips README.md and episodes.md (master list, not a topic file).
    Returns a defaultdict so missing slugs safely return [].
    """
    index_dir = dataset_dir / "index"
    if not index_dir.is_dir():
        raise FileNotFoundError(f"Index directory not found: {index_dir}")

    slug_to_topics: dict[str, list[str]] = defaultdict(list)
    skip_files = {"readme.md", "episodes.md"}

    for md_file in sorted(index_dir.glob("*.md")):
        if md_file.name.lower() in skip_files:
            continue

        topic = _topic_from_filename(md_file.name)
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not read %s: %s", md_file, exc)
            continue

        slugs = _LINK_RE.findall(text)
        for slug in slugs:
            slug_to_topics[slug].append(topic)

        logger.debug("Topic '%s': %d episodes", topic, len(slugs))

    logger.info(
        "Parsed %d topic files, covering %d unique episodes",
        sum(1 for f in index_dir.glob("*.md") if f.name.lower() not in skip_files),
        len(slug_to_topics),
    )
    return dict(slug_to_topics)
