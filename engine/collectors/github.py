"""GitHub radar: new / fast-growing AI repos via the public search API.

No key required (60 req/hour unauthenticated). GITHUB_TOKEN raises the limit.
Never crashes the pipeline: all network errors -> ([], warning string).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import requests

from engine.processors.normalize import make_event, validate_event

API = "https://api.github.com/search/repositories"


def collect(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    g = (cfg.get("sources") or {}).get("github", {})
    if not g.get("enabled", True):
        return [], "disabled"
    queries = g.get("queries", ["artificial-intelligence stars:>500"])
    per_q = int(g.get("per_query_limit", 15))
    timeout = int(g.get("timeout", 15))
    token = cfg.get("github_token", "")

    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ai-radar/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    events: List[Dict[str, Any]] = []
    warnings: List[str] = []
    try:
        for q in queries:
            try:
                r = requests.get(
                    API,
                    params={"q": q, "sort": "updated", "order": "desc", "per_page": per_q},
                    headers=headers,
                    timeout=timeout,
                )
                if r.status_code == 403:
                    warnings.append("rate-limited")
                    break
                r.raise_for_status()
                items = (r.json() or {}).get("items", [])
            except Exception as e:  # per-query failure must not kill run
                warnings.append(f"query failed: {e}")
                continue
            for repo in items:
                try:
                    ev = make_event(
                        title=repo.get("full_name", "unknown"),
                        url=repo.get("html_url", ""),
                        source="GitHub",
                        source_type="github",
                        description=repo.get("description") or "",
                        author=(repo.get("owner") or {}).get("login", ""),
                        # pushed_at = actual activity signal (created_at is years old for popular repos)
                        published_at=repo.get("pushed_at", "") or repo.get("updated_at", "") or repo.get("created_at", "") or "",
                        tags=[t for t in [repo.get("language", "")] if t],
                        raw_data={
                            "stars": repo.get("stargazers_count", 0),
                            "forks": repo.get("forks_count", 0),
                            "language": repo.get("language", ""),
                            "open_issues": repo.get("open_issues_count", 0),
                            "updated_at": repo.get("updated_at", ""),
                            "pushed_at": repo.get("pushed_at", ""),
                        },
                    )
                    if not validate_event(ev):
                        events.append(ev)
                except Exception:
                    continue
    except Exception as e:
        return events, f"error: {e}"
    # de-dup repos appearing in several queries (by url)
    seen, uniq = set(), []
    for ev in events:
        if ev["url"] in seen:
            continue
        seen.add(ev["url"])
        uniq.append(ev)
    note = "; ".join(warnings) if warnings else "ok"
    return uniq, note
