"""Official AI company blogs collector.

V1 implementation = RSS-based (same engine as rss.py, different config key).
Keeps lab announcements primary-sourced without fragile scraping.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from engine.processors.normalize import make_event, validate_event


def collect(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    b = (cfg.get("sources") or {}).get("official_blogs", {})
    if not b.get("enabled", True):
        return [], "disabled"
    per_feed = int(b.get("max_per_feed", 8))
    events: List[Dict[str, Any]] = []
    warnings: List[str] = []
    try:
        from engine.collectors.feedutil import fetch_feed
    except ImportError as e:
        return [], f"feedutil missing: {e}"

    for src in b.get("sources", []) or []:
        if not src.get("enabled", True):
            continue
        name = src.get("name", "Blog")
        url = src.get("url", "")
        if not url:
            continue
        try:
            feed = fetch_feed(url, int(b.get("timeout", 15)))
            for e in (feed.entries or [])[:per_feed]:
                try:
                    link = getattr(e, "link", "") or ""
                    if not link:
                        continue
                    ev = make_event(
                        title=getattr(e, "title", "") or "(untitled)",
                        url=link, source=name, source_type="rss",
                        description=(getattr(e, "summary", "") or "")[:1500],
                        author=getattr(e, "author", "") or name,
                        published_at=getattr(e, "published", "") or getattr(e, "updated", "") or "",
                        tags=["official", src.get("category", "news")],
                        raw_data={"feed": name, "feed_url": url, "official": True},
                    )
                    if not validate_event(ev):
                        # only direct lab feeds count as official; aggregator hits don't
                        if src.get("official", True):
                            ev["tags"] = list(dict.fromkeys(ev["tags"] + ["official-release"]))
                        events.append(ev)
                except Exception:
                    continue
        except Exception as e:
            warnings.append(f"{name}: {e}")
    note = "; ".join(warnings) if warnings else "ok"
    return events, note
