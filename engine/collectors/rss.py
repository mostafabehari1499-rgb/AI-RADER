"""Generic RSS/Atom collector (feedparser). Used for `rss:` sources in sources.yaml."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from engine.processors.normalize import make_event, validate_event


def _parse(url: str, timeout: int):
    from engine.collectors.feedutil import fetch_feed
    return fetch_feed(url, timeout)


def collect(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    r = (cfg.get("sources") or {}).get("rss", {})
    if not r.get("enabled", True):
        return [], "disabled"
    timeout = int(r.get("timeout", 15))
    per_feed = int(r.get("max_per_feed", 10))
    events: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for src in r.get("sources", []) or []:
        if not src.get("enabled", True):
            continue
        name = src.get("name", "RSS")
        url = src.get("url", "")
        if not url:
            continue
        try:
            feed = _parse(url, timeout)
            entries = getattr(feed, "entries", [])[:per_feed]
            if getattr(feed, "bozo", False) and not entries:
                warnings.append(f"{name}: parse failed")
                continue
            for e in entries:
                try:
                    link = getattr(e, "link", "") or ""
                    title = getattr(e, "title", "") or "(untitled)"
                    desc = getattr(e, "summary", "") or getattr(e, "description", "") or ""
                    published = getattr(e, "published", "") or getattr(e, "updated", "") or ""
                    author = getattr(e, "author", "") or ""
                    tags = []
                    try:
                        for t in getattr(e, "tags", []) or []:
                            term = t.get("term") if isinstance(t, dict) else getattr(t, "term", "")
                            if term:
                                tags.append(str(term))
                    except Exception:
                        pass
                    ev = make_event(
                        title=title, url=link, source=name, source_type="rss",
                        description=desc[:1500], author=author,
                        published_at=published, tags=tags[:10],
                        raw_data={"feed": name, "feed_url": url,
                                  "category_hint": src.get("category", "")},
                    )
                    if ev["url"] and not validate_event(ev):
                        events.append(ev)
                except Exception:
                    continue
        except Exception as e:
            warnings.append(f"{name}: {e}")
            continue
    note = "; ".join(warnings) if warnings else "ok"
    return events, note
