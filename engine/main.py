"""AI RADAR main pipeline.

  python -m engine.main            # full run (collect -> notify -> store)
  python -m engine.main --dry-run  # collect+analyze, no Telegram, no commit-relevant writes to state notified
  python -m engine.main --demo     # no network, no keys: fake events verify pipeline+dashboard data

Collectors run concurrently; one failure = WARNING, never CRASH.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from engine.config import ROOT, load_config
from engine.processors import classify as classify_m
from engine.processors import deduplicate as dedup_m
from engine.processors import experiment_finder as exp_m
from engine.processors import score as score_m
from engine.processors import summarize as summ_m
from engine.processors.normalize import utcnow_iso
from engine.storage import json_store

COLLECTORS = [
    ("github", "engine.collectors.github"),
    ("huggingface", "engine.collectors.huggingface"),
    ("openrouter", "engine.collectors.openrouter"),
    ("arxiv", "engine.collectors.arxiv"),
    ("civitai", "engine.collectors.civitai"),
    ("hackernews", "engine.collectors.hackernews"),
    ("reddit", "engine.collectors.reddit"),
    ("rss", "engine.collectors.rss"),
    ("official_blogs", "engine.collectors.official_blogs"),
    ("youtube", "engine.collectors.youtube"),
]


def log(level: str, msg: str) -> None:
    print(f"[{level}] {msg}", flush=True)


def _import(path: str):
    import importlib
    return importlib.import_module(path)


def run_collectors(cfg: dict):
    collected, notes = {}, {}
    with ThreadPoolExecutor(max_workers=len(COLLECTORS)) as ex:
        futs = {}
        for name, mod_path in COLLECTORS:
            try:
                mod = _import(mod_path)
                futs[ex.submit(mod.collect, cfg)] = name
            except Exception as e:
                collected[name] = []
                notes[name] = f"import failed: {e}"
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                events, note = fut.result()
                collected[name] = events or []
                notes[name] = note or "ok"
            except Exception as e:
                collected[name] = []
                notes[name] = f"error: {e}"
    return collected, notes


def demo_events() -> list:
    now = utcnow_iso()
    raw = [
        {"title": "XYZ-7B — open LLM release", "url": "https://huggingface.co/example/xyz-7b",
         "source": "Hugging Face", "source_type": "huggingface",
         "description": "Open-weights 7B chat model with Apache 2.0 license. Demo space available.",
         "author": "example", "published_at": now, "tags": ["llm", "open-source", "open weights"],
         "raw_data": {"likes": 850, "downloads": 45000, "model_id": "example/xyz-7b"}},
        {"title": "XYZ-7B inference server", "url": "https://github.com/example/xyz-inference",
         "source": "GitHub", "source_type": "github",
         "description": "Fast inference server for XYZ-7B with Docker and Colab notebook.",
         "author": "example", "published_at": now, "tags": ["python"],
         "raw_data": {"stars": 3200, "forks": 300, "language": "Python"}},
        {"title": "Efficient reasoning via distillation", "url": "https://arxiv.org/abs/2601.00001",
         "source": "arXiv", "source_type": "arxiv",
         "description": "Paper on distilling reasoning traces into 3B student models with benchmarks.",
         "author": "A. Researcher", "published_at": now, "tags": ["cs.CL"],
         "raw_data": {"authors": ["A. Researcher"]}},
        {"title": "Testing XYZ-7B live (video)", "url": "https://www.youtube.com/watch?v=demo1234567",
         "source": "YouTube · Example AI Channel", "source_type": "youtube",
         "description": "Hands-on live test of XYZ-7B with prompts and honest verdict.",
         "author": "Example AI Channel", "published_at": now, "tags": ["video", "tutorial"],
         "raw_data": {"thumbnail": ""}},
        {"title": "Lab announces new video model", "url": "https://example.com/blog/new-video-model",
         "source": "Example AI Blog", "source_type": "rss",
         "description": "Official announcement of a text-to-video model with public demo waitlist.",
         "author": "Example", "published_at": now, "tags": ["official-release", "video"],
         "raw_data": {"official": True}},
    ]
    from engine.processors.normalize import make_event
    out = []
    for r in raw:
        ev = make_event(r["title"], r["url"], r["source"], r["source_type"],
                        r["description"], r["author"], r["published_at"], r["tags"], r["raw_data"])
        out.append(ev)
    return out


def _metrics(ev: dict) -> dict:
    raw = ev.get("raw_data", {}) or {}
    return {"stars": int(raw.get("stars", 0) or 0),
            "downloads": int(raw.get("downloads", 0) or 0),
            "likes": int(raw.get("likes", 0) or 0),
            "sources": len(ev.get("merged_sources", [ev.get("source", "")]))}


def pipeline(cfg: dict, raw_events: list, notes: dict, demo: bool = False,
             history: dict | None = None, max_ai: int = 12) -> dict:
    total = len(raw_events)
    unique, dups = dedup_m.deduplicate(raw_events)
    classify_m.classify_all(unique, cfg.get("keywords", {}))
    exp_m.attach_experiments(unique)
    score_m.score_all(unique, priors=history or {})
    # AI only for important+ (keeps free-tier usage tiny)
    important = [e for e in unique if int(e.get("importance_score", 0) or 0) >= 40]
    summ_m.analyze(important if not demo else unique,
                   api_key="" if demo else cfg.get("gemini_api_key", ""),
                   model=cfg.get("gemini_model", "gemini-2.0-flash"),
                   max_ai=max_ai)
    # ensure every event has ai card
    for ev in unique:
        if "ai" not in ev:
            ev["ai"] = summ_m._deterministic(ev)
    return {"events": unique, "duplicates": dups, "total": total, "notes": notes}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AI RADAR pipeline")
    ap.add_argument("--demo", action="store_true", help="fake events, no network, no Telegram")
    ap.add_argument("--dry-run", action="store_true", help="real collection, but no Telegram sends")
    ap.add_argument("--limit-ai", type=int, default=12)
    args = ap.parse_args(argv)

    cfg = load_config(ROOT)
    root = Path(cfg["root"])
    state = json_store.load_state(root)
    prev_ids = set(state.get("notified_ids", []))
    prev_urls = set(state.get("notified_urls", []))

    if args.demo:
        log("INFO", "demo mode: generating fake events (no network)")
        raw, notes = demo_events(), {"demo": "ok"}
    else:
        collected, notes = run_collectors(cfg)
        for name, evs in collected.items():
            log("INFO", f"{name}: {len(evs)} items ({notes.get(name,'')})")
        raw = [e for evs in collected.values() for e in evs]

    report = pipeline(cfg, raw, notes, demo=args.demo,
                      history=None if (args.demo or args.dry_run) else state.get("history", {}),
                      max_ai=args.limit_ai)
    events = report["events"]

    # filter already-notified (avoid duplicate Telegram messages across runs):
    # an event is skipped if its id OR its url was ever successfully sent
    fresh = [e for e in events
             if e.get("id") not in prev_ids and e.get("url", "") not in prev_urls]

    sent = 0
    if args.demo or args.dry_run:
        log("INFO", "Telegram skipped (demo/dry-run)")
    else:
        from engine.notifications import telegram as tg
        token, chat = cfg["telegram_bot_token"], cfg["telegram_chat_id"]
        if token and chat:
            sendable = [e for e in fresh if int(e.get("importance_score", 0) or 0) >= cfg["telegram_min_score"]]
            sent, failed = tg.send_alerts(sendable, token, chat, cfg["telegram_min_score"])
            if failed:
                log("WARNING", f"Telegram: {failed} message(s) failed to send")
                log("WARNING", tg.diagnose(token, chat))
            if cfg["daily_digest"] and events:
                tg.send_message(token, chat, tg.format_digest(
                    [e for e in events if int(e.get("importance_score", 0) or 0) >= 60]))
        else:
            log("WARNING", "Telegram secrets missing — alerts skipped")

    # persist
    if args.demo:
        # demo writes ONLY to the dashboard preview — never to production data/
        by_score = sorted(events, key=lambda e: e.get("importance_score", 0), reverse=True)
        json_store.save_json(root / "dashboard" / "data" / "events.json", by_score)
    elif args.dry_run:
        log("INFO", "dry-run: storage untouched")
    else:
        json_store.merge_events(root, events, retention_days=cfg.get("retention_days", 90))
        # mirror for GitHub Pages (dashboard/ is the published dir)
        try:
            all_ev = json.loads((root / "data" / "events.json").read_text(encoding="utf-8"))
            json_store.save_json(root / "dashboard" / "data" / "events.json", all_ev[:300])
            for name in ("trending.json", "models.json"):
                p = root / "data" / name
                if p.exists():
                    json_store.save_json(root / "dashboard" / "data" / name,
                                         json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:
            log("WARNING", f"pages mirror failed: {e}")
        notified = prev_ids | {e["id"] for e in events if e.get("notified")}
        notified_urls = prev_urls | {e.get("url", "") for e in events if e.get("notified") and e.get("url")}
        # lightweight cross-run history: per-event metric snapshots enable
        # measured trend velocity on subsequent runs (no database needed)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        history = state.get("history", {})
        for e in events:
            eid = e.get("id", "")
            if not eid:
                continue
            prev = history.get(eid, {})
            history[eid] = {"first_seen": prev.get("first_seen", now),
                            "last_seen": now, "metrics": _metrics(e)}
        # prune: keep entries seen within retention window or ever notified
        from datetime import timedelta
        keep_since = (datetime.now(timezone.utc) - timedelta(days=max(1, int(cfg.get("retention_days", 90))))).isoformat()
        history = {k: v for k, v in history.items()
                   if (v.get("last_seen", "") >= keep_since) or (k in notified)}
        history = dict(list(history.items())[-2000:])
        state.update({
            "last_run": now,
            "notified_ids": sorted(notified)[-500:],
            "notified_urls": sorted(notified_urls)[-500:],
            "history": history,
            "last_counts": {"total": report["total"], "unique": len(events),
                            "duplicates": report["duplicates"], "sent": sent},
        })
        json_store.save_state(root, state)
        json_store.save_json(root / "data" / "sources.json", notes)

    important = sum(1 for e in events if int(e.get("importance_score", 0) or 0) >= 60)
    log("INFO", f"Total: {report['total']}")
    log("INFO", f"Duplicates: {report['duplicates']}")
    log("INFO", f"Important: {important}")
    log("INFO", f"Telegram alerts: {sent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
