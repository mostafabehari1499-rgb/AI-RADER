"""Deterministic keyword classifier. No network, no LLM.

Assigns primary `category` + `subcategories` from title/description/tags/source.
Rules come from config/categories.yaml (keywords map); source_type gives priors.
"""
from __future__ import annotations

from typing import Any, Dict, List


def _text(ev: Dict[str, Any]) -> str:
    parts = [ev.get("title", ""), ev.get("description", ""),
             " ".join(ev.get("tags", [])), ev.get("source", "")]
    return " ".join(parts).lower()


def classify_event(ev: Dict[str, Any], keywords: Dict[str, List[str]] | None = None) -> Dict[str, Any]:
    keywords = keywords or {}
    text = _text(ev)
    hits: List[str] = []
    for kw, cats in keywords.items():
        if kw.lower() in text:
            for c in cats:
                if c not in hits:
                    hits.append(c)

    # source-type priors
    st = ev.get("source_type", "")
    if st == "github" and "GITHUB" not in hits:
        hits.append("GITHUB")
    if st == "arxiv" and "RESEARCH" not in hits:
        hits.insert(0, "RESEARCH")
    if st == "youtube":
        if "VIDEO" not in hits:
            hits.append("VIDEO")
        if "tutorial" in text and "TUTORIAL" not in hits:
            hits.append("TUTORIAL")
    if st == "huggingface" and "MODEL" not in hits:
        # spaces are tools/demos; models are MODEL
        if "space" in text:
            hits.insert(0, "TOOL")
        else:
            hits.insert(0, "MODEL")
    if st == "openrouter" and "MODEL" not in hits:
        hits.insert(0, "MODEL")
    if st == "civitai":
        if "VIDEO" not in hits and "video" in text:
            hits.insert(0, "VIDEO")
        elif "IMAGE" not in hits:
            hits.insert(0, "IMAGE")
    if st in ("hackernews", "reddit") and not hits:
        hits = ["NEWS"]

    if "open-source" in text or "open source" in text or "open weights" in text:
        if "OPEN_SOURCE" not in hits:
            hits.append("OPEN_SOURCE")
    if "github.com" in (ev.get("url", "") or "") and "OPEN_SOURCE" not in hits:
        hits.append("OPEN_SOURCE")

    if not hits:
        # generic news fallback for rss
        hits = ["NEWS"] if st == "rss" else ["OTHER"]

    ev["category"] = hits[0]
    ev["subcategories"] = hits[1:6]
    return ev


def classify_all(events: List[Dict[str, Any]], keywords: Dict[str, List[str]] | None = None) -> List[Dict[str, Any]]:
    return [classify_event(ev, keywords) for ev in events]
