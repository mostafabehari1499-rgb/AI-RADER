"""arXiv radar: recent AI papers via the official export API (no key needed).

API: http://export.arxiv.org/api/query?search_query=...&sortBy=submittedDate
Parses Atom XML with stdlib xml to avoid extra dependencies.
"""
from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Tuple

import requests

from engine.processors.normalize import make_event, validate_event

API = "http://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}


def _strip_html(t: str) -> str:
    t = re.sub(r"\s+", " ", (t or "")).strip()
    return t[:1500]


def collect(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    a = (cfg.get("sources") or {}).get("arxiv", {})
    if not a.get("enabled", True):
        return [], "disabled"
    queries = a.get("queries", ["cat:cs.CL AND llm"])
    max_results = int(a.get("max_results", 15))
    timeout = int(a.get("timeout", 20))
    events: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for q in queries:
        try:
            params = {
                "search_query": q,
                "start": 0,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
            url = API + "?" + urllib.parse.urlencode(params)
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "ai-radar/1.0"})
            r.raise_for_status()
            root = ET.fromstring(r.text)
        except Exception as e:
            warnings.append(f"query failed: {e}")
            continue
        for entry in root.findall("a:entry", NS):
            try:
                title = _strip_html((entry.findtext("a:title", "", NS) or ""))
                abstract = _strip_html((entry.findtext("a:summary", "", NS) or ""))
                link = entry.findtext("a:id", "", NS) or ""
                published = entry.findtext("a:published", "", NS) or ""
                authors = [au.findtext("a:name", "", NS) for au in entry.findall("a:author", NS)]
                authors = [x for x in authors if x][:5]
                cats = [c.get("term", "") for c in entry.findall("a:category", NS)]
                ev = make_event(
                    title=title,
                    url=link.strip(),
                    source="arXiv",
                    source_type="arxiv",
                    description=abstract,
                    author=", ".join(authors),
                    published_at=published,
                    tags=[c for c in cats if c][:8],
                    raw_data={"authors": authors, "categories": cats, "query": q},
                )
                if not validate_event(ev):
                    events.append(ev)
            except Exception:
                continue

    # dedup by url across queries
    seen, uniq = set(), []
    for ev in events:
        if ev["url"] in seen:
            continue
        seen.add(ev["url"])
        uniq.append(ev)
    note = "; ".join(warnings) if warnings else "ok"
    return uniq, note
