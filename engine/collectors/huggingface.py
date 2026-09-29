"""Hugging Face radar: newest / trending models + trending Spaces.

Uses the public HF API (no key required):
  GET https://huggingface.co/api/models?sort=lastModified&direction=-1&limit=N
  GET https://huggingface.co/api/spaces?sort=likes&direction=-1&limit=N
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import requests

from engine.processors.normalize import make_event, validate_event

MODELS_API = "https://huggingface.co/api/models"
SPACES_API = "https://huggingface.co/api/spaces"


def _get(url: str, params: dict, timeout: int):
    r = requests.get(url, params=params, timeout=timeout,
                     headers={"User-Agent": "ai-radar/1.0"})
    r.raise_for_status()
    return r.json()


def collect(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    h = (cfg.get("sources") or {}).get("huggingface", {})
    if not h.get("enabled", True):
        return [], "disabled"
    timeout = int(h.get("timeout", 15))
    m_limit = int(h.get("models_limit", 30))
    s_limit = int(h.get("spaces_limit", 15))
    events: List[Dict[str, Any]] = []
    warnings: List[str] = []

    try:
        models = _get(MODELS_API, {"sort": "lastModified", "direction": "-1", "limit": m_limit}, timeout)
    except Exception as e:
        return [], f"models api failed: {e}"
    for m in models if isinstance(models, list) else []:
        try:
            mid = m.get("modelId") or m.get("id") or ""
            if not mid:
                continue
            likes = m.get("likes", 0) or 0
            downloads = m.get("downloads", 0) or 0
            tags = [t for t in (m.get("tags") or []) if isinstance(t, str)][:10]
            ev = make_event(
                title=mid,
                url=f"https://huggingface.co/{mid}",
                source="Hugging Face",
                source_type="huggingface",
                description=f"Tags: {', '.join(tags[:5])}" if tags else "",
                author=mid.split("/")[0] if "/" in mid else "",
                # lastModified = activity signal (createdAt is stale for popular models)
                published_at=m.get("lastModified", "") or m.get("createdAt", "") or "",
                tags=tags,
                raw_data={
                    "model_id": mid,
                    "likes": likes,
                    "downloads": downloads,
                    "pipeline_tag": m.get("pipeline_tag", ""),
                    "library": m.get("library_name", ""),
                    "last_modified": m.get("lastModified", ""),
                    "gated": bool(m.get("gated", False)),
                },
            )
            if not validate_event(ev):
                events.append(ev)
        except Exception:
            continue

    try:
        spaces = _get(SPACES_API, {"sort": "likes", "direction": "-1", "limit": s_limit}, timeout)
    except Exception as e:
        warnings.append(f"spaces api failed: {e}")
        spaces = []
    for s in spaces if isinstance(spaces, list) else []:
        try:
            sid = s.get("id", "")
            if not sid:
                continue
            ev = make_event(
                title=f"Space: {sid}",
                url=f"https://huggingface.co/spaces/{sid}",
                source="Hugging Face Spaces",
                source_type="huggingface",
                description=(s.get("cardData") or {}).get("title", "") if isinstance(s.get("cardData"), dict) else "",
                author=sid.split("/")[0] if "/" in sid else "",
                published_at=s.get("lastModified", "") or s.get("createdAt", "") or "",
                tags=["space", "demo"],
                raw_data={
                    "space_id": sid,
                    "likes": s.get("likes", 0) or 0,
                    "sdk": (s.get("sdk") or ""),
                    "last_modified": s.get("lastModified", ""),
                    "space_url": f"https://huggingface.co/spaces/{sid}",
                },
            )
            if not validate_event(ev):
                events.append(ev)
        except Exception:
            continue

    note = "; ".join(warnings) if warnings else "ok"
    return events, note
