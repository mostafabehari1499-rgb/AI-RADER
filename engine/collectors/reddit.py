"""Reddit radar: AI community posts via public .json endpoints (keyless).

Subreddits are configurable. Uses a proper User-Agent; 429s degrade to a
warning, never a crash.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import requests

from engine.processors.normalize import make_event, validate_event


def _iso(ts) -> str:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return ""


def collect(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    r0 = (cfg.get("sources") or {}).get("reddit", {})
    if not r0.get("enabled", True):
        return [], "disabled"
    timeout = int(r0.get("timeout", 15))
    per_sub = int(r0.get("max_per_sub", 8))
    min_score = int(r0.get("min_score", 5))
    events: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for sub in r0.get("subreddits", []) or []:
        if not sub.get("enabled", True) or not sub.get("name"):
            continue
        name = sub["name"]
        try:
            r = requests.get(f"https://www.reddit.com/r/{name}/new/.json",
                             params={"limit": per_sub * 2}, timeout=timeout,
                             headers={"User-Agent": "ai-radar/1.0 (personal research)"})
            if r.status_code == 429:
                warnings.append(f"r/{name}: rate-limited")
                continue
            r.raise_for_status()
            children = ((r.json() or {}).get("data") or {}).get("children", [])
        except Exception as e:
            warnings.append(f"r/{name}: {type(e).__name__}")
            continue
        n = 0
        for c in children:
            if n >= per_sub:
                break
            try:
                d = c.get("data", {}) or {}
                if d.get("stickied") or d.get("removed_by_category"):
                    continue
                score = int(d.get("score", 0) or 0)
                if score < min_score:
                    continue
                title = d.get("title", "") or "(untitled)"
                ev = make_event(
                    title=title,
                    url="https://www.reddit.com" + (d.get("permalink", "") or ""),
                    source=f"Reddit · r/{name}", source_type="reddit",
                    description=(d.get("selftext", "") or "")[:1200],
                    author=d.get("author", ""),
                    published_at=_iso(d.get("created_utc", 0)),
                    tags=["reddit", "discussion", name.lower()],
                    raw_data={"subreddit": name, "score": score,
                              "comments": int(d.get("num_comments", 0) or 0)},
                )
                if ev["url"] != "https://www.reddit.com" and not validate_event(ev):
                    events.append(ev)
                    n += 1
            except Exception:
                continue
    return events, ("; ".join(warnings) if warnings else "ok")
