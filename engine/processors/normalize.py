"""Canonical Event schema + normalization.

Every collector MUST return a list of Event dicts shaped like this:

{
  "id": "...",            # deterministic, set by deduplicate.py (may be empty pre-dedup)
  "title": "...",
  "url": "...",
  "source": "github",     # human source name, e.g. "GitHub", "Hugging Face"
  "source_type": "github|huggingface|youtube|arxiv|rss",
  "published_at": "...",  # ISO-8601 string (may be "")
  "discovered_at": "...", # ISO-8601 UTC set at collection time
  "category": "...",      # primary category, set by classify.py
  "subcategories": [],
  "description": "...",
  "author": "...",
  "tags": [],
  "raw_data": {}
}
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List

VALID_SOURCE_TYPES = {"github", "huggingface", "youtube", "arxiv", "rss"}

_WS = re.compile(r"\s+")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation/extra spaces for identity comparison."""
    t = (title or "").lower()
    t = re.sub(r"[^a-z0-9\u0600-\u06ff ]", " ", t)
    t = _WS.sub(" ", t).strip()
    return t


def make_event(
    title: str,
    url: str,
    source: str,
    source_type: str,
    description: str = "",
    author: str = "",
    published_at: str = "",
    tags: List[str] | None = None,
    raw_data: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(f"bad source_type: {source_type}")
    return {
        "id": "",
        "title": (title or "").strip()[:300],
        "url": (url or "").strip(),
        "source": source,
        "source_type": source_type,
        "published_at": published_at or "",
        "discovered_at": utcnow_iso(),
        "category": "OTHER",
        "subcategories": [],
        "description": (description or "").strip()[:2000],
        "author": author or "",
        "tags": list(tags or [])[:20],
        "raw_data": dict(raw_data or {}),
    }


def validate_event(ev: Dict[str, Any]) -> List[str]:
    """Return a list of problems (empty = valid). Collectors must pass this."""
    problems = []
    for key in ("title", "url", "source", "source_type"):
        if not ev.get(key):
            problems.append(f"missing {key}")
    if ev.get("source_type") not in VALID_SOURCE_TYPES:
        problems.append("bad source_type")
    return problems
