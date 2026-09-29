"""Shared feed fetching with HARD timeouts.

feedparser.parse(url) performs its own HTTP fetch with no usable timeout,
so a black-holing host can stall a run indefinitely. We fetch with
requests (which honors timeout=) and hand the bytes to feedparser.
"""
from __future__ import annotations

import requests


def fetch_feed(url: str, timeout: int = 15):
    """Return feedparser-parsed feed. Raises on network/HTTP errors."""
    import feedparser
    r = requests.get(url, timeout=timeout,
                     headers={"User-Agent": "ai-radar/1.0",
                              "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
    r.raise_for_status()
    return feedparser.parse(r.content)
