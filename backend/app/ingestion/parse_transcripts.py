"""
parse_transcripts.py
~~~~~~~~~~~~~~~~~~~~
Walk dataset/episodes/*/transcript.md and parse each file into a dict
containing the YAML frontmatter fields and the raw transcript body.

Frontmatter schema (from the dataset's README.md / CLAUDE.md):
  guest, title, youtube_url, video_id, publish_date, description,
  duration_seconds, duration, view_count, channel, keywords[]

The body starts immediately after the closing `---` delimiter.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Fields we pull from frontmatter (the subset the DB cares about).
_FRONTMATTER_FIELDS = {
    "guest",
    "title",
    "youtube_url",
    "video_id",
    "publish_date",
    "description",
    "duration_seconds",
    "view_count",
    "keywords",
}

# Regex to split a file into frontmatter + body.
# Matches:  ---\n<yaml>\n---\n<body>
_FM_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n(.*)", re.DOTALL)


def parse_transcript(path: Path) -> dict[str, Any] | None:
    """Parse a single transcript.md file.

    Returns a dict with keys:
      meta  — dict of frontmatter fields (only the subset we need)
      body  — the raw transcript text (everything after the second ---)
      slug  — the guest-folder name (e.g. 'brian-chesky')

    Returns None if the file cannot be parsed (logged as a warning).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None

    match = _FM_RE.match(text)
    if not match:
        logger.warning("No valid YAML frontmatter in %s", path)
        return None

    fm_raw, body = match.group(1), match.group(2)

    try:
        fm = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError as exc:
        logger.warning("YAML parse error in %s: %s", path, exc)
        return None

    # Keep only the fields the DB schema needs.
    meta = {k: fm.get(k) for k in _FRONTMATTER_FIELDS}

    # Minimal validation: guest and title are required.
    if not meta.get("guest") or not meta.get("title"):
        logger.warning("Missing guest/title in %s", path)
        return None

    slug = path.parent.name  # e.g. 'brian-chesky'
    return {"meta": meta, "body": body.strip(), "slug": slug}


def walk_episodes(dataset_dir: Path) -> list[dict[str, Any]]:
    """Parse all transcript.md files under dataset_dir/episodes/.

    Returns a list of parsed transcript dicts (skips malformed files).
    """
    episodes_dir = dataset_dir / "episodes"
    if not episodes_dir.is_dir():
        raise FileNotFoundError(f"Episodes directory not found: {episodes_dir}")

    results: list[dict[str, Any]] = []
    # Sort for deterministic ordering.
    for guest_dir in sorted(episodes_dir.iterdir()):
        transcript = guest_dir / "transcript.md"
        if not transcript.is_file():
            logger.debug("No transcript.md in %s, skipping", guest_dir)
            continue
        parsed = parse_transcript(transcript)
        if parsed is not None:
            results.append(parsed)

    logger.info("Parsed %d transcripts from %s", len(results), episodes_dir)
    return results
