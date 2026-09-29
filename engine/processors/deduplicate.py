"""Deduplication + cross-source clustering.

Same AI release often appears on GitHub + HF + YouTube + blogs.
We merge those into ONE canonical event with multiple sources.

Strategy (deterministic, no LLM):
  1. canonical key = normalized model/repo-ish token OR normalized title.
  2. event id = sha1(canonical key)[:16].
  3. cluster events sharing the key -> keep the richest (longest description
     wins), merge `merged_sources` + `merged_urls` lists.
"""
from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Tuple
from urllib.parse import urlparse

from engine.processors.normalize import normalize_title

_MODEL_PAT = re.compile(r"\b([a-z0-9][a-z0-9\-_]{1,60}-(?:7b|8b|13b|34b|70b|405b|1b|3b|mini|small|base|large|xl|7-8b))\b", re.I)
_REPO_PAT = re.compile(r"github\.com/([^/\s?#]+/[^/\s?#]+)", re.I)
_HF_PAT = re.compile(r"huggingface\.co/(?:spaces/)?([^?\s#]+)", re.I)


def canonical_key(ev: Dict) -> str:
    title = ev.get("title", "") or ""
    url = ev.get("url", "") or ""
    norm = normalize_title(title)
    m = _MODEL_PAT.search(title)
    if m:
        return "model:" + m.group(1).lower()
    m = _REPO_PAT.search(url)
    if m:
        return "repo:" + m.group(1).lower().rstrip("/")
    m = _HF_PAT.search(url)
    if m:
        return "hf:" + m.group(1).lower().rstrip("/")
    # fallback: first 8 significant words of normalized title
    stop = {"the", "a", "an", "new", "with", "for", "and", "from", "using"}
    words = [w for w in norm.split() if w not in stop][:8]
    host = urlparse(url).netloc.lower() if url else ""
    return f"title:{' '.join(words)}|{host}"


def event_id_for(key: str) -> str:
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def deduplicate(events: List[Dict]) -> Tuple[List[Dict], int]:
    """Return (unique_events, duplicates_removed). Mutates dicts in place."""
    buckets: Dict[str, List[Dict]] = {}
    for ev in events:
        key = canonical_key(ev)
        eid = event_id_for(key)
        ev["id"] = eid
        ev["cluster_id"] = eid
        buckets.setdefault(key, []).append(ev)

    unique: List[Dict] = []
    removed = 0
    for key, group in buckets.items():
        if len(group) == 1:
            ev = group[0]
            ev["merged_sources"] = [ev.get("source", "")]
            ev["merged_urls"] = [ev.get("url", "")]
            unique.append(ev)
            continue
        # keep richest
        group.sort(key=lambda e: (len(e.get("description", "")), len(e.get("raw_data", {}))), reverse=True)
        primary = group[0]
        primary["merged_sources"] = sorted({g.get("source", "") for g in group if g.get("source")})
        primary["merged_urls"] = [g.get("url", "") for g in group if g.get("url")]
        primary["tags"] = sorted(set(sum([g.get("tags", []) for g in group], [])))[:20]
        # keep best raw signals
        merged_raw = {}
        for g in group:
            merged_raw.update(g.get("raw_data", {}) or {})
        primary["raw_data"] = merged_raw
        removed += len(group) - 1
        unique.append(primary)
    return unique, removed
