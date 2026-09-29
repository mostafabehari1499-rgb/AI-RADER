"""Hacker News radar: AI discussions via the official Firebase API (keyless).

  GET /v0/newstories.json -> ids -> GET /item/<id>.json
Only items matching AI keywords become events (title + url text).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import requests

from engine.processors.normalize import make_event, validate_event

BASE = "https://hacker-news.firebaseio.com/v0"
AI_KEYS = ("ai", "llm", "gpt", "agent", "diffusion", "robot", "nvidia", "openai",
           "anthropic", "huggingface", "hugging face", "stable diffusion", "gemini",
           "claude", "midjourney", "deepseek", "llama", "mistral", "sora", "mcp",
           "copilot", "neural", "transformer", "rag ", " quantized", "kokoro")


def _iso(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return ""


def collect(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    h = (cfg.get("sources") or {}).get("hackernews", {})
    if not h.get("enabled", True):
        return [], "disabled"
    timeout = int(h.get("timeout", 10))
    max_items = int(h.get("max_items", 20))
    check = int(h.get("check_latest", 40))
    try:
        ids = requests.get(f"{BASE}/newstories.json", timeout=timeout,
                           headers={"User-Agent": "ai-radar/1.0"}).json()[:check]
    except Exception as e:
        return [], f"api failed: {e}"

    events: List[Dict[str, Any]] = []
    for i in ids if isinstance(ids, list) else []:
        if len(events) >= max_items:
            break
        try:
            it = requests.get(f"{BASE}/item/{i}.json", timeout=timeout,
                              headers={"User-Agent": "ai-radar/1.0"}).json() or {}
            if it.get("type") != "story" or it.get("dead"):
                continue
            title = it.get("title", "")
            link = it.get("url", "") or f"https://news.ycombinator.com/item?id={i}"
            if not any(k in f"{title} {link}".lower() for k in AI_KEYS):
                continue
            ev = make_event(
                title=title, url=link, source="Hacker News", source_type="hackernews",
                description=f"{it.get('score', 0)} points, {it.get('descendants', 0)} comments on HN.",
                author=it.get("by", ""), published_at=_iso(it.get("time", 0)),
                tags=["news", "discussion", "hackernews"],
                raw_data={"hn_id": i, "score": it.get("score", 0),
                          "comments": it.get("descendants", 0),
                          "hn_url": f"https://news.ycombinator.com/item?id={i}"},
            )
            if not validate_event(ev):
                events.append(ev)
        except Exception:
            continue
    return events, "ok"
