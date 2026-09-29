"""Transparent deterministic scoring: importance (0-100) + trend.

Importance signals (additive, capped at 100):
  recency ............ +22 / +15 / +8 by age (ISO-8601 or RFC-2822 dates)
  source quality ..... +5 high-priority source (via raw_data.source_priority)
  cross-source ....... +15 if merged from >=2 sources, +23 total if >=3
  github stars ....... +22 / +17 / +13 / +9 / +5 by tier
  HF downloads ....... +16 / +13 / +10 / +6 / +3 by tier; likes +6 / +4 / +2
  official release ... +10 (tag official-release)
  open-source ........ +8 (tags or category)
  free demo .......... +8 (experiment finder found a real option)
  technical depth .... +5 (arxiv paper)

Trend (single-run SIGNAL, not measured velocity — see state history):
  trend_score 0-100 from recency + cross-source + popularity + history growth
  trend_status: STABLE / RISING / HOT / VIRAL (signal labels, need history to confirm)
  trend_basis: "single-run-signal" or "history-compared" when a prior snapshot exists

Pure functions -> easy to unit test, no LLM involved.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Tuple


def _parse_dt(s: str):
    if not s:
        return None
    s = str(s).strip()
    try:
        # ISO-8601 (GitHub, Hugging Face, arXiv, internal)
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        # RFC-2822 (RSS/Atom feeds, e.g. "Mon, 28 Sep 2026 19:00:00 GMT")
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _age_hours(ev: Dict) -> float | None:
    for key in ("published_at", "discovered_at"):
        dt = _parse_dt(ev.get(key, ""))
        if dt:
            delta = datetime.now(timezone.utc) - dt
            return max(0.0, delta.total_seconds() / 3600.0)
    return None


def score_importance(ev: Dict) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []
    raw = ev.get("raw_data", {}) or {}
    tags = [t.lower() for t in ev.get("tags", [])]

    age = _age_hours(ev)
    if age is not None:
        if age <= 24:
            score += 22; reasons.append("Published in last 24h")
        elif age <= 48:
            score += 15; reasons.append("Published in last 48h")
        elif age <= 168:
            score += 8; reasons.append("Published this week")

    merged = ev.get("merged_sources", [ev.get("source", "")])
    if len(merged) >= 3:
        score += 23; reasons.append(f"Detected in {len(merged)} sources")
    elif len(merged) == 2:
        score += 15; reasons.append("Multiple sources detected")

    stars = int(raw.get("stars", 0) or 0)
    if stars >= 100000:
        score += 22; reasons.append(f"{stars:,} GitHub stars")
    elif stars >= 20000:
        score += 17; reasons.append(f"{stars:,} GitHub stars")
    elif stars >= 5000:
        score += 13; reasons.append(f"{stars:,} GitHub stars")
    elif stars >= 1000:
        score += 9
    elif stars >= 200:
        score += 5

    dl = int(raw.get("downloads", 0) or 0)
    likes = int(raw.get("likes", 0) or 0)
    if dl >= 1000000:
        score += 16; reasons.append(f"{dl:,} HF downloads")
    elif dl >= 200000:
        score += 13; reasons.append(f"{dl:,} HF downloads")
    elif dl >= 50000:
        score += 10; reasons.append(f"{dl:,} HF downloads")
    elif dl >= 5000:
        score += 6
    elif dl >= 500:
        score += 3
    if likes >= 5000:
        score += 6; reasons.append(f"{likes:,} HF likes")
    elif likes >= 1000:
        score += 4
    elif likes >= 200:
        score += 2

    if "official-release" in tags or "official" in tags:
        score += 10; reasons.append("Official release")
    cats = [str(ev.get("category", "")).lower().replace("-", "_")] + \
           [str(c).lower().replace("-", "_") for c in ev.get("subcategories", [])]
    if "open_source" in tags or "open-source" in tags or "open_source" in cats:
        score += 8; reasons.append("Open-source")
    if ev.get("source_type") == "arxiv":
        score += 5; reasons.append("Peer-track research paper")
    if ev.get("experiment", {}).get("can_test_free"):
        score += 8; reasons.append("Free demo available")

    # source priority hint
    prio = str(raw.get("source_priority", "")).lower()
    if prio == "high":
        score += 5; reasons.append("High-priority source")

    return min(100, score), reasons


def importance_level(score: int) -> str:
    if score >= 90:
        return "BREAKING"
    if score >= 75:
        return "HIGH"
    if score >= 60:
        return "IMPORTANT"
    if score >= 40:
        return "NORMAL"
    return "LOW"


def score_trend(ev: Dict, prior: Dict | None = None) -> Tuple[int, str, str]:
    """prior = previous snapshot {stars, downloads, likes, sources} from state history.
    Without history this is a single-run SIGNAL (trend_basis accordingly)."""
    raw = ev.get("raw_data", {}) or {}
    score = 0
    age = _age_hours(ev)
    if age is not None:
        if age <= 12:
            score += 40
        elif age <= 24:
            score += 32
        elif age <= 72:
            score += 22
        elif age <= 168:
            score += 12
        else:
            score += 4
    merged = ev.get("merged_sources", [ev.get("source", "")])
    if len(merged) >= 3:
        score += 30
    elif len(merged) == 2:
        score += 18
    stars = int(raw.get("stars", 0) or 0)
    if stars >= 20000:
        score += 15
    elif stars >= 5000:
        score += 10
    elif stars >= 1000:
        score += 6
    dl = int(raw.get("downloads", 0) or 0)
    if dl >= 100000:
        score += 15
    elif dl >= 10000:
        score += 8
    basis = "single-run-signal"
    if prior:
        # measured growth since last snapshot -> real velocity evidence
        def _grew(now: int, was: int, rel: float = 0.05, floor: int = 20) -> bool:
            return now - was >= max(floor, int(was * rel))
        if _grew(stars, int(prior.get("stars", 0) or 0)):
            score += 10
        if _grew(dl, int(prior.get("downloads", 0) or 0), floor=500):
            score += 8
        if _grew(int(raw.get("likes", 0) or 0), int(prior.get("likes", 0) or 0), floor=10):
            score += 4
        if len(merged) > int(prior.get("sources", 0) or 0):
            score += 6
        basis = "history-compared"
    score = min(100, score)
    if score >= 80:
        status = "VIRAL"
    elif score >= 60:
        status = "HOT"
    elif score >= 40:
        status = "RISING"
    else:
        status = "STABLE"
    return score, status, basis


def score_all(events: List[Dict], priors: Dict[str, Dict] | None = None) -> List[Dict]:
    priors = priors or {}
    for ev in events:
        imp, reasons = score_importance(ev)
        trend, status, basis = score_trend(ev, (priors.get(ev.get("id", "")) or {}).get("metrics"))
        ev["importance_score"] = imp
        ev["importance_reasons"] = reasons
        ev["importance_level"] = importance_level(imp)
        ev["trend_score"] = trend
        ev["trend_status"] = status
        ev["trend_basis"] = basis
    # most important first
    events.sort(key=lambda e: (e.get("importance_score", 0), e.get("trend_score", 0)), reverse=True)
    return events
