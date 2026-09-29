"""Free experiment finder — NEVER invents links.

Looks for real, verifiable free-testing avenues attached to the event:
  1. Hugging Face model/Space URL itself (is a free page/demo)
  2. Space URL inside raw_data
  3. github repo (free code, possible demo links in description)
  4. colab/kaggle/playground URLs literally present in text
  5. arxiv paper -> code search hint (no fabricated link; can_test_free=False
     unless a concrete URL exists)

Returns {"can_test_free": bool, "confidence": ..., "options": [...],
         "hardware": {...}, "note": ...}
Hardware tiers are rough estimates, always labelled "estimated".
"""
from __future__ import annotations

import re
from typing import Dict, List

_URL = re.compile(r"https?://[^\s)\"']+")


def _opt(name: str, otype: str, url: str) -> Dict:
    return {"name": name, "type": otype, "url": url, "status": "available"}


def find_experiments(ev: Dict) -> Dict:
    url = ev.get("url", "") or ""
    text = f"{ev.get('description','')} {' '.join(ev.get('tags',[]))}"
    raw = ev.get("raw_data", {}) or {}
    options: List[Dict] = []

    low = url.lower()
    if "huggingface.co/spaces/" in low:
        options.append(_opt("Hugging Face Space", "huggingface_space", url))
    elif "huggingface.co/" in low and ev.get("source_type") == "huggingface":
        options.append(_opt("Hugging Face model page", "huggingface_model", url))
    if raw.get("space_url"):
        if all(o["url"] != raw["space_url"] for o in options):
            options.append(_opt("Hugging Face Space", "huggingface_space", raw["space_url"]))

    # explicit free-playground links mentioned in text (only real URLs found)
    for m in _URL.findall(text):
        ml = m.lower()
        if "colab.research.google.com" in ml:
            options.append(_opt("Google Colab", "colab", m))
        elif "kaggle.com" in ml:
            options.append(_opt("Kaggle", "kaggle", m))
        elif "huggingface.co/spaces" in ml:
            if all(o["url"] != m for o in options):
                options.append(_opt("Hugging Face Space", "huggingface_space", m))

    if "github.com" in low:
        options.append(_opt("GitHub repo (code + setup)", "github_repo", url))

    # de-dup by url
    seen, uniq = set(), []
    for o in options:
        if o["url"] in seen:
            continue
        seen.add(o["url"])
        uniq.append(o)

    can_free = len(uniq) > 0
    confidence = "high" if any(o["type"] == "huggingface_space" for o in uniq) else ("medium" if uniq else "low")

    note = ""
    if not can_free:
        if ev.get("source_type") == "arxiv":
            note = "Paper only — no demo link found in metadata."
        else:
            note = "No verifiable free testing link found."

    return {
        "can_test_free": can_free,
        "confidence": confidence,
        "options": uniq[:6],
        "hardware": estimate_hardware(ev),
        "note": note,
    }


def estimate_hardware(ev: Dict) -> Dict:
    """Rough, explicitly-estimated tiers. Never presented as official specs."""
    text = f"{ev.get('title','')} {ev.get('description','')}".lower()
    # guess param size
    params = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*b\b", text)
    if m:
        try:
            params = float(m.group(1))
        except Exception:
            params = None
    def tier(n: float | None) -> Dict[str, str]:
        base = {"label": "estimated", "cpu": "POSSIBLE", "ram8": "POSSIBLE",
                "vram8": "POSSIBLE", "vram16": "EASY", "cloud_demo": "POSSIBLE"}
        if n is None:
            return base
        if n <= 3:
            return {"label": "estimated", "cpu": "POSSIBLE", "ram8": "EASY",
                    "vram8": "EASY", "vram16": "EASY", "cloud_demo": "EASY"}
        if n <= 8:
            return {"label": "estimated", "cpu": "DIFFICULT", "ram8": "POSSIBLE",
                    "vram8": "POSSIBLE", "vram16": "EASY", "cloud_demo": "EASY"}
        if n <= 14:
            return {"label": "estimated", "cpu": "NOT PRACTICAL", "ram8": "DIFFICULT",
                    "vram8": "DIFFICULT", "vram16": "POSSIBLE", "cloud_demo": "POSSIBLE"}
        return {"label": "estimated", "cpu": "NOT PRACTICAL", "ram8": "NOT PRACTICAL",
                "vram8": "NOT PRACTICAL", "vram16": "DIFFICULT", "cloud_demo": "POSSIBLE"}
    hw = tier(params)
    hw["params_b"] = params
    return hw


def attach_experiments(events: List[Dict]) -> List[Dict]:
    for ev in events:
        ev["experiment"] = find_experiments(ev)
    return events
