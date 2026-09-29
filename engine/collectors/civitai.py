"""Civitai radar: new community image/video models (SDXL, Flux, LoRA...).

Official keyless API: https://civitai.com/api/v1/models?limit=N&sort=Newest
NSFW entries are skipped (content-safe by default).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import requests

from engine.processors.normalize import make_event, validate_event

API = "https://civitai.com/api/v1/models"


def collect(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    c = (cfg.get("sources") or {}).get("civitai", {})
    if not c.get("enabled", True):
        return [], "disabled"
    timeout = int(c.get("timeout", 20))
    limit = int(c.get("models_limit", 25))
    try:
        r = requests.get(API, params={"limit": limit, "sort": "Newest"},
                         timeout=timeout, headers={"User-Agent": "ai-radar/1.0"})
        r.raise_for_status()
        items = (r.json() or {}).get("items", [])
    except Exception as e:
        return [], f"api failed: {e}"

    events: List[Dict[str, Any]] = []
    for m in items if isinstance(items, list) else []:
        try:
            if m.get("nsfw"):
                continue
            mid = m.get("id")
            if not mid:
                continue
            stats = m.get("stats", {}) or {}
            creator = (m.get("creator", {}) or {}).get("username", "")
            mtype = m.get("type", "")
            bases = m.get("baseModels", []) or []
            base = bases[0] if bases else ""
            ver = (m.get("modelVersions", {}) or [{}])[0] if isinstance(m.get("modelVersions"), list) else {}
            published = ver.get("publishedAt", "") or ""
            if not base:
                base = ver.get("baseModel", "") or ""
            content_tags = [t for t in (m.get("tags", []) or []) if isinstance(t, str)][:6]
            likes = int(stats.get("thumbsUpCount", 0) or 0)
            ev = make_event(
                title=f"{m.get('name', 'untitled')} [{mtype}/{base}]".strip(),
                url=f"https://civitai.com/models/{mid}",
                source="Civitai",
                source_type="civitai",
                description=(m.get("description", "") or "")[:1000],
                author=creator,
                published_at=published,
                tags=[t for t in [mtype, base, "image", "civitai"] + content_tags if t][:10],
                raw_data={
                    "model_id": mid,
                    "downloads": int(stats.get("downloadCount", 0) or 0),
                    "likes": likes,
                    "comments": int(stats.get("commentCount", 0) or 0),
                    "model_type": mtype,
                },
            )
            if not validate_event(ev):
                events.append(ev)
        except Exception:
            continue
    return events, "ok"
