"""OpenRouter radar: newly released models on a major public platform.

Uses the official keyless public API:
  GET https://openrouter.ai/api/v1/models
Returns 400+ models with created timestamps, pricing, context window.
Only models newer than max_age_days become events (configurable).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import requests

from engine.processors.normalize import make_event, validate_event

API = "https://openrouter.ai/api/v1/models"


def _iso(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return ""


def collect(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    o = (cfg.get("sources") or {}).get("openrouter", {})
    if not o.get("enabled", True):
        return [], "disabled"
    timeout = int(o.get("timeout", 20))
    limit = int(o.get("models_limit", 25))
    max_age = int(o.get("max_age_days", 14))
    try:
        r = requests.get(API, timeout=timeout, headers={"User-Agent": "ai-radar/1.0"})
        r.raise_for_status()
        models = (r.json() or {}).get("data", [])
    except Exception as e:
        return [], f"api failed: {e}"

    now = datetime.now(timezone.utc).timestamp()
    fresh = []
    for m in models if isinstance(models, list) else []:
        try:
            created = int(m.get("created", 0) or 0)
            if created and (now - created) > max_age * 86400:
                continue
            fresh.append((created, m))
        except Exception:
            continue
    fresh.sort(key=lambda x: x[0], reverse=True)

    events: List[Dict[str, Any]] = []
    for created, m in fresh[:limit]:
        try:
            mid = m.get("id", "")
            if not mid:
                continue
            pricing = m.get("pricing", {}) or {}
            try:
                free = float(pricing.get("prompt", "1") or "1") == 0
            except Exception:
                free = False
            author = mid.split("/")[0] if "/" in mid else ""
            tags = ["openrouter", "model"]
            if free:
                tags.append("free")
            ev = make_event(
                title=m.get("name", mid) or mid,
                url=f"https://openrouter.ai/{mid}",
                source="OpenRouter",
                source_type="openrouter",
                description=(m.get("description", "") or "")[:1500],
                author=author,
                published_at=_iso(created),
                tags=tags,
                raw_data={
                    "model_id": mid,
                    "created": created,
                    "context_length": m.get("context_length", 0) or 0,
                    "prompt_price": pricing.get("prompt", ""),
                    "completion_price": pricing.get("completion", ""),
                    "free": free,
                    "hugging_face_id": m.get("hugging_face_id") or "",
                },
            )
            if not validate_event(ev):
                events.append(ev)
        except Exception:
            continue
    return events, "ok"
