"""AI analysis: bilingual summaries + content angles.

Pipeline rule: only important events reach this stage (caller filters).
Uses GEMINI_API_KEY when present (free-tier friendly, 1 short call per event,
capped). Otherwise falls back to deterministic templates — pipeline NEVER
crashes because AI is unavailable.

Produces on each event `ai` dict:
  summary_en, summary_ar, what, why, whats_new, who, can_test,
  content_score, content_formats, video_titles, video_angles, experiment_ideas
"""
from __future__ import annotations

from typing import Dict, List

FORMATS = ["NEWS", "TUTORIAL", "LIVE TEST", "DEEP DIVE", "COMPARISON", "SHORT", "EXPERIMENT", "BEGINNER GUIDE"]


def _creator_score(ev: Dict) -> int:
    """Creator opportunity 0-100. NOT a virality/revenue prediction — ranks how
    practical this event is to turn into useful content: new + free + demoable
    + educational + novel."""
    s = 40
    age_note = ev.get("published_at", "") or ev.get("discovered_at", "")
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(str(age_note).replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - dt).days <= 3:
            s += 15  # newness
    except Exception:
        pass
    exp = ev.get("experiment", {}) or {}
    if exp.get("can_test_free"):
        s += 15  # free accessibility + demonstrability
    if ev.get("trend_status") in ("HOT", "VIRAL"):
        s += 8
    if ev.get("category") in ("MODEL", "AGENT", "TOOL"):
        s += 7  # practical usefulness
    if "TUTORIAL" in (ev.get("subcategories", []) + [ev.get("category", "")]):
        s += 5  # educational value
    return max(0, min(100, s))


def _deterministic(ev: Dict) -> Dict:
    title = ev.get("title", "Untitled")
    cat = ev.get("category", "OTHER")
    src = ev.get("source", "")
    exp = ev.get("experiment", {}) or {}
    opts = ", ".join(o["name"] for o in exp.get("options", [])[:3]) or "no verified free demo found yet"
    summary_en = f"{title} ({cat}) via {src}. " + (ev.get("description", "")[:220] or "New AI release tracked by AI RADAR.")
    return {
        "summary_en": summary_en,
        "summary_ar": f"رصد رادار الذكاء الاصطناعي: {title} عبر {src}. {('يمكن تجربته: ' + opts) if exp.get('can_test_free') else 'لا يوجد رابط تجربة مجاني مؤكد بعد.'}",
        "what": f"{title} — reported by {src}.",
        "why": f"Categorized as {cat} with importance {ev.get('importance_score', 0)}/100: " + "; ".join(ev.get("importance_reasons", [])[:3]),
        "whats_new": (ev.get("description", "")[:300] or "See source link for details."),
        "who": "AI builders, students, and content creators following open AI releases.",
        "can_test": opts,
        "content_score": _content_score(ev),
        "content_formats": _formats(ev),
        "video_titles": [f"I tested {title} so you don't have to", f"{title} explained in 10 minutes",
                         f"Is {title} actually good? Honest test"],
        "video_angles": ["Potentially useful content angle: live first-test + honest verdict.",
                         "Potentially useful content angle: beginner-friendly setup walkthrough."],
        "experiment_ideas": [f"Try the free option ({opts}) and record what breaks.",
                             "Compare against one well-known baseline on the same prompt."],
        "creator_opportunity_score": _creator_score(ev),
        "content_angle": f"Hands-on look at {title}: what it does, who it helps, and whether the free option works.",
        "target_audience": "AI-curious builders, students, and practitioners following open AI releases.",
        "experiment_angle": f"Run the free option ({opts}) on 3 fixed prompts and score the outputs.",
        "tutorial_angle": f"Beginner setup guide: from zero to first working result with {title}.",
        "comparison_angle": f"{title} vs the best-known alternative on the same task, same prompts.",
        "ai_model": "deterministic-fallback",
    }


def _content_score(ev: Dict) -> int:
    s = int(ev.get("importance_score", 0) or 0)
    if (ev.get("experiment", {}) or {}).get("can_test_free"):
        s += 6
    if ev.get("trend_status") in ("HOT", "VIRAL"):
        s += 6
    if ev.get("source_type") == "youtube":
        s += 2
    return max(0, min(100, s))


def _formats(ev: Dict) -> List[str]:
    out = []
    if (ev.get("experiment", {}) or {}).get("can_test_free"):
        out += ["LIVE TEST", "TUTORIAL", "SHORT"]
    if ev.get("source_type") == "arxiv":
        out += ["DEEP DIVE", "BEGINNER GUIDE"]
    if ev.get("category") == "MODEL":
        out += ["COMPARISON", "EXPERIMENT"]
    out.append("NEWS")
    seen = list(dict.fromkeys(out))
    return seen[:4]


def _gemini(ev: Dict, api_key: str, model: str = "gemini-2.0-flash") -> Dict | None:
    """One short Gemini call (+1 retry with backoff). None on any failure."""
    import time as _t
    for attempt in (0, 1):
        try:
            import json as _json
            import urllib.request
            prompt = (
                "You are an AI news analyst. Reply with strict JSON only, keys: "
                "summary_en, summary_ar, what, why, whats_new, who, can_test, video_titles(3), video_angles(2), experiment_ideas(2). "
                "Only state facts supported by the event data below; use 'unknown' where unsure. "
                f"Event: {ev.get('title')} | source {ev.get('source')} | category {ev.get('category')} | "
                f"description: {(ev.get('description','') or '')[:800]}"
            )
            body = _json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=" + api_key,
                data=body, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=25) as r:
                data = _json.loads(r.read().decode())
            text = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0].get("text", "")
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                return None
            parsed = _json.loads(text[start:end + 1])
            base = _deterministic(ev)
            for k in ("summary_en", "summary_ar", "what", "why", "whats_new", "who", "can_test"):
                if parsed.get(k):
                    base[k] = str(parsed[k])[:600]
            for k in ("video_titles", "video_angles", "experiment_ideas"):
                if isinstance(parsed.get(k), list) and parsed[k]:
                    base[k] = [str(x)[:160] for x in parsed[k][:3]]
            base["ai_model"] = model
            return base
        except Exception:
            if attempt == 0:
                _t.sleep(2)  # one exponential-ish retry, then fallback
            continue
    return None


def analyze(events: List[Dict], api_key: str = "", max_ai: int = 12,
            model: str = "gemini-2.0-flash") -> List[Dict]:
    """Analyze top events (caller pre-filters). Caps AI calls at max_ai."""
    targets = sorted(events, key=lambda e: e.get("importance_score", 0), reverse=True)[:max_ai]
    ids = {id(e) for e in targets}
    for ev in events:
        if id(ev) not in ids:
            # light deterministic card for the long tail (no AI call)
            ev["ai"] = _deterministic(ev)
            ev["ai"]["ai_model"] = "deterministic-skipped"
            continue
        ai = _gemini(ev, api_key, model) if api_key else None
        ev["ai"] = ai or _deterministic(ev)
    return events
