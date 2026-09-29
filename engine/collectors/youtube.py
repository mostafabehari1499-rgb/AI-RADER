"""YouTube radar — works WITHOUT an API key via channel RSS feeds.

For each configured channel:
  https://www.youtube.com/feeds/videos.xml?channel_id=<ID>

If YOUTUBE_API_KEY is set, search_terms are ALSO queried via the Data API
(optional enhancement; RSS path always runs first).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import requests

from engine.processors.normalize import make_event, validate_event


def _rss_videos(channel_id: str, timeout: int) -> list:
    from engine.collectors.feedutil import fetch_feed
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed = fetch_feed(url, timeout)
    return feed.entries or []


def collect(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    y = (cfg.get("sources") or {}).get("youtube", {})
    if not y.get("enabled", True):
        return [], "disabled"
    timeout = int(y.get("timeout", 15))
    per_ch = int(y.get("max_per_channel", 6))
    events: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for ch in y.get("channels", []) or []:
        if not ch.get("enabled", True):
            continue
        cid = ch.get("channel_id", "")
        name = ch.get("name", "YouTube")
        if not cid:
            warnings.append(f"{name}: missing channel_id")
            continue
        try:
            entries = _rss_videos(cid, timeout)[:per_ch]
        except Exception as e:
            warnings.append(f"{name}: {e}")
            continue
        for e in entries:
            try:
                link = getattr(e, "link", "") or ""
                title = getattr(e, "title", "") or "(untitled)"
                thumb = ""
                try:
                    media = getattr(e, "media_thumbnail", None)
                    if media:
                        thumb = media[0].get("url", "") if isinstance(media[0], dict) else ""
                except Exception:
                    thumb = ""
                ev = make_event(
                    title=title, url=link, source=f"YouTube · {name}",
                    source_type="youtube",
                    description=(getattr(e, "summary", "") or "")[:1000],
                    author=name,
                    published_at=getattr(e, "published", "") or getattr(e, "updated", "") or "",
                    tags=["video", "youtube"],
                    raw_data={"channel": name, "channel_id": cid, "thumbnail": thumb},
                )
                if ev["url"] and not validate_event(ev):
                    events.append(ev)
            except Exception:
                continue

    # Optional Data API enhancement
    api_key = cfg.get("youtube_api_key", "")
    if api_key:
        try:
            for term in (y.get("search_terms", []) or [])[:3]:
                try:
                    r = requests.get(
                        "https://www.googleapis.com/youtube/v3/search",
                        params={"part": "snippet", "q": term, "type": "video",
                                "maxResults": 5, "order": "date", "key": api_key},
                        timeout=timeout,
                    )
                    if r.status_code != 200:
                        warnings.append(f"yt api: http {r.status_code}")
                        break
                    for it in (r.json().get("items", []) or []):
                        vid = ((it.get("id") or {}).get("videoId")) or ""
                        sn = it.get("snippet", {}) or {}
                        if not vid:
                            continue
                        ev = make_event(
                            title=sn.get("title", "(untitled)"),
                            url=f"https://www.youtube.com/watch?v={vid}",
                            source=f"YouTube · search:{term}",
                            source_type="youtube",
                            description=sn.get("description", "")[:1000],
                            author=sn.get("channelTitle", ""),
                            published_at=sn.get("publishedAt", ""),
                            tags=["video", "youtube", "search"],
                            raw_data={"thumbnail": (sn.get("thumbnails", {}).get("medium") or {}).get("url", "")},
                        )
                        if not validate_event(ev):
                            events.append(ev)
                except Exception as e:
                    warnings.append(f"yt search failed: {e}")
        except Exception:
            pass

    note = "; ".join(warnings) if warnings else "ok"
    return events, note
