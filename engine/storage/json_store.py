"""Tiny JSON storage layer. No database server needed.

data/events.json   — newest-first list (capped at MAX_EVENTS)
data/trending.json — top by trend_score
data/models.json   — subset category==MODEL
data/sources.json  — last run report per source
data/state.json    — run state (last_run, notified ids, counts)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

MAX_EVENTS = 500


def _p(root: Path, name: str) -> Path:
    return root / "data" / name


def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_state(root: Path) -> Dict[str, Any]:
    return load_json(_p(root, "state.json"), {})


def save_state(root: Path, state: Dict[str, Any]) -> None:
    save_json(_p(root, "state.json"), state)


def merge_events(root: Path, new_events: List[Dict], retention_days: int = 90) -> List[Dict]:
    """Prepend new (by id), drop dup ids, prune older than retention_days, cap size."""
    from datetime import datetime, timezone
    existing = load_json(_p(root, "events.json"), [])
    by_id = {e.get("id"): e for e in existing if e.get("id")}
    for ev in new_events:
        if not ev.get("id"):
            continue
        if ev["id"] not in by_id:
            by_id[ev["id"]] = ev
        else:
            # refresh the stored copy with this run's evidence (scores, trend
            # basis, metrics, analysis) but keep the original discovery time
            stored = by_id[ev["id"]]
            for k in ("importance_score", "importance_reasons", "importance_level",
                      "trend_score", "trend_status", "trend_basis", "category",
                      "subcategories", "tags", "merged_sources", "merged_urls",
                      "raw_data", "experiment", "ai", "description"):
                if ev.get(k) is not None:
                    stored[k] = ev[k]
    cutoff = ""
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, int(retention_days)))).isoformat()
    except Exception:
        cutoff = ""
    kept = [e for e in by_id.values()
            if not cutoff or (e.get("discovered_at", "") or "") >= cutoff or not e.get("discovered_at")]
    all_ev = sorted(kept,
                    key=lambda e: (e.get("discovered_at", ""), e.get("importance_score", 0)),
                    reverse=True)[:MAX_EVENTS]
    save_json(_p(root, "events.json"), all_ev)
    trending = sorted(all_ev, key=lambda e: e.get("trend_score", 0), reverse=True)[:100]
    save_json(_p(root, "trending.json"), trending)
    models = [e for e in all_ev if e.get("category") == "MODEL"][:200]
    save_json(_p(root, "models.json"), models)
    return all_ev
