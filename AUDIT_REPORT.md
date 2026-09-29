# AI RADAR V1 — AUDIT REPORT

Date: 2026-09-29 · Auditor role: independent deep audit (did not trust prior report)
Method: inspected code, ran syntax/tests/demo/live dry-run, probed every
collector, injected failures, fixed safe issues, re-ran everything.

## 1. Executive summary

The system is **real and working**: 6/6 collectors fetch live data (216–221
events/run), pipeline stages all execute, 20/20 tests pass, dashboard renders.
The audit found **two P1 defects** (run-hang risk, duplicate-alert risk) and
**two P2 defects** (score inflation, mislabeled sources) — **all fixed and
re-verified**. One P0 is a **user action**: three live secrets were pasted into
chat and must be rotated (details §15, values never reproduced here).
Telegram/Gemini **live** sends were deliberately NOT tested with those
compromised keys — marked BLOCKED with exact setup steps in USER_ACTIONS.md.

## 2. Actual architecture (verified from code)

```
INTERNET
→ engine/collectors/{github,huggingface,arxiv,rss,official_blogs,youtube}.py
  → .collect(cfg) -> (raw_events, note)          [ThreadPoolExecutor, main.py]
→ engine/processors/normalize.py: make_event / validate_event
→ engine/processors/deduplicate.py: canonical_key → event_id/cluster_id, merge
→ engine/processors/classify.py: classify_event (YAML keywords + priors)
→ engine/processors/experiment_finder.py: find_experiments (real URLs only)
→ engine/processors/score.py: score_importance + score_trend (+history growth)
→ engine/processors/summarize.py: analyze (Gemini if key, else deterministic)
→ engine/storage/json_store.py: merge_events (+retention) → data/*.json
→ engine/notifications/telegram.py: send_alerts (threshold-gated)
→ dashboard/{index.html,app.js,style.css} reads dashboard/data/*.json
→ .github/workflows/radar.yml: schedule → run → commit data → push
```

| Stage | File:function | In | Out | On failure |
|---|---|---|---|---|
| Collect | collectors/*.py:collect | cfg | (events, note) | ([], warning), never crash |
| Normalize | normalize.py:make_event | raw fields | Event dict | ValueError on bad source_type |
| Dedup | deduplicate.py:deduplicate | events | (unique, removed) | pure fn, no I/O |
| Classify | classify.py:classify_event | event+keywords | category+subs | falls back OTHER/NEWS |
| Experiment | experiment_finder.py | event | can_test_free+options | can_test_free=false |
| Score | score.py:score_all | events+priors | scores/levels/trend | pure fn |
| AI | summarize.py:analyze | top events | ai card | deterministic fallback |
| Store | json_store.py:merge_events | events | JSON views | corrupt file → defaults |
| Notify | telegram.py:send_alerts | events≥threshold | sent count | False, no exception |
| UI | dashboard/app.js | data/*.json | cards/filters | empty-state message |

## 3. What was verified

- 44 files present, entry `python -m engine.main` with `--demo/--dry-run` ✓
- `compileall` PASS; unittest 20/20 + pytest 20/20 ✓
- Demo: 5 fake events → 3 unique, 0 Telegram sends ✓
- Live dry-run: 221 events, 6/6 collectors ok, no Telegram, no storage writes ✓
- Schema: 0 bad events, 0 bad URLs across all collectors ✓
- Dedup: 4/4 controlled cases (same-URL, GH+HF model, unrelated) ✓
- Experiment links: 6/6 sampled URLs return HTTP 200 (none fabricated) ✓
- Score distribution live: min 0 / median 27 / max 60 — no inflation ✓
- 15 categories assigned; free-test found for 75/192 events ✓
- Feed timeout fix: refused host now fails in <20 s (was: indefinite hang) ✓
- No secrets in any repo file; `.env` absent; `.env.example` placeholders ✓

## 4. What was NOT verified (honest gaps)

- Telegram live send (BLOCKED: token compromised + no chat id on file)
- Gemini live call (BLOCKED: key compromised; must not use)
- GitHub Actions execution (no repo access used; YAML statically valid)
- Browser console/mobile rendering (no browser here; JS passes `node --check`)
- Remote git history (no local clone; PAT in chat was not used)

## 5. Test results

- Before fixes: 12/12. After fixes: **20/20** (8 new regression tests).
- 1 failure encountered mid-audit (old storage test used stale Jan dates vs new
  90-day retention) — fixture updated to relative dates, re-green.
- Quality: REAL behavior tests (dedup clustering, scoring tiers, telegram
  format, storage merge, experiment detection, config load, date parsing,
  timeout, trend basis, creator fields, retention). No mock-only theater.
  Missing: collector HTTP tests (require network by nature — covered by live
  dry-run instead).

## 6. Collector results (live probe)

| Collector | n | Time | Schema | Source type | Notes |
|---|---|---|---|---|---|
| GitHub | 54–59 | ~3 s | 100% | Official API, keyless | fresh (pushed today); rate-limit handled; token optional |
| Hugging Face | 45 | ~2.5 s | 100% | Official API | 15/45 lack descriptions (tagless models) — cosmetic |
| arXiv | 57 | ~4 s | 100% | Official API | sorted by submittedDate — old-as-breaking risk: low |
| RSS | 30 | ~4 s | 100% | RSS/Atom | OpenAI/HF/Google feeds healthy |
| Official blogs | 24 | ~2 s | 100% | Google News RSS | press coverage, NOT primary — renamed honestly |
| YouTube | 6 | ~1 s | 100% | Channel RSS | 1 placeholder channel; no global coverage without API key |

## 7. Data quality

- URLs: 0 invalid. Dates: ISO + RFC-2822 both parsed (fixed). 15 HF + 10 RSS
  items lack descriptions (accepted, shown as-is, never invented).
- Press items link `news.google.com` redirect URLs, not primary articles —
  disclosed in dashboard via source name; primary-source preference documented.

## 8. Deduplication — GOOD

Model-key (`xyz-7b`), repo-key, HF-key, title-fallback. Live demo merged 3
sources into 1 canonical event with `merged_sources/merged_urls`. Controlled
4/4. Live runs show ~0 merges (keys rarely collide in one window) — expected;
  cross-run + cross-source merges grow as history accumulates.

## 9. Scoring — GOOD, no inflation

Factors: recency 22/15/8 · stars 22–5 · downloads 16–3 · likes 6–2 ·
cross-source 15/23 · official 10 · open-source 8 · free demo 8 · arxiv 5.
Live: 2 IMPORTANT / 29 NORMAL / 161 LOW. Top item (206k-star repo pushed
today) = 60. Thresholds BREAKING 90 / HIGH 75 / IMPORTANT 60 per spec.

## 10. Trend limitations — SIGNAL, not velocity (improved)

Was single-run only. Now: per-event metric snapshots in `state.json`
`history` (stars/downloads/likes/sources + first/last seen, capped 2000,
retention-pruned) feed a measured growth bonus; every event carries
`trend_basis: single-run-signal | history-compared` (live run: 192/192
single-run — honest). HOT/VIRAL remain signal labels until history confirms.

## 11. Gemini configuration

- Code path: `summarize.py:_gemini`, default `gemini-2.0-flash` (Flash-class,
  cheap), overridable via **`GEMINI_MODEL`** (new; wired through config,
  `.env.example`, workflow vars). Short JSON prompts (≤800 chars context),
  top-12 events max, 1 retry + 2 s backoff, quota/invalid-key → deterministic
  bilingual fallback (verified 0.7 s with bad key). Anti-hallucination
  instruction ("use 'unknown' where unsure") added to prompt.
- Live call: BLOCKED (key compromised — rotate first).

## 12. Telegram configuration

- Format verified offline: bilingual, links, emoji, 640-char compact alert +
  digest; matches spec sections (§18/§29). Missing-creds → instant False;
  unreachable host → False in ~1 s, no exceptions.
- Dedup guard: notified IDs persisted — **but `data/state.json` was gitignored,
  so Actions runs would have re-sent every alert (P1, FIXED: now committed,
  contains zero secrets).**
- Live send: BLOCKED — needs fresh token + chat id (USER_ACTIONS.md).

## 13. Dashboard

`node --check` clean; 17 filters incl. Saved (localStorage); search + 4 sorts;
detail modal (AR/EN, hardware-estimated, content ideas, source links);
dual data paths (`./data`, `../data`) cover Pages + local; preview data valid
(3 demo events with ai+experiment cards). Browser-console check BLOCKED.

## 14. GitHub Actions

YAML valid: schedule `*/30` + dispatch, `contents: write`, setup-python 3.11,
pip install, secrets via env (never echoed), commits only `data/` +
`dashboard/data/`. Now also passes GEMINI_MODEL/RETENTION_DAYS vars and
persists state.json. Execution itself BLOCKED (not run here).

## 15. Security findings

- Repo files: CLEAN (pattern sweep: 0 hits; `.env` absent; state holds no secrets).
- **P0 — secrets pasted in chat (Telegram token, GitHub PAT, Gemini key):**
  treat as compromised. Rotate: BotFather `/revoke`; new Gemini key; PAT was
  1-hour scoped — confirm expiry, delete it. Never commit keys; use Secrets.
- Remote history not inspected (PAT not used) — if keys were ever pushed,
  rotation (above) already covers it.

## 16. Performance

Full live dry-run ≈ **7 s** (concurrent collectors; slowest ~4 s). AI stage 0 s
without key. No optimization needed.

## 17. P0 issues — 1 (user action, not code)

1. **Rotate the three chat-exposed secrets** (see §15).

## 18. P1 issues — 2, both FIXED + re-verified

1. **Feed fetch ignored timeouts** (`feedparser.parse(url)` can hang forever;
   proven by audit probe hanging twice) → new `collectors/feedutil.py`
   (requests fetch with timeout → parse bytes); all 3 RSS consumers migrated.
2. **`data/state.json` gitignored → duplicate Telegram alerts every Actions
   run** → un-ignored (secret-free by construction) so notified-ids + history
   persist.

## 19. P2 issues — 2, both FIXED

1. **RFC-2822 dates unparsed → every RSS/blog item scored as "last 24h"**
   (+22 inflation) → `email.utils` fallback in `_parse_dt`.
2. **Aggregator results labeled as official blogs** → renamed
   "Anthropic/DeepMind/Meta AI — press", `official: false` honored.

## 20. P3 improvements — done

`GEMINI_MODEL` env, `RETENTION_DAYS` (default 90) with pruning in storage +
history, `trend_basis`, `creator_opportunity_score` + 5 creator angle fields,
retry/backoff + anti-hallucination prompt line, workflow var passthrough.

## 21. Exact user actions required → see USER_ACTIONS.md

## 22. Exact next development steps

1. Rotate secrets → configure GitHub Secrets → safe Telegram test.
2. Push, enable Actions + Pages, first live run, confirm 1 digest, no dupes.
3. Replace placeholder YouTube channel with 5–10 followed channels.
4. After ~10 runs, verify `trend_basis: history-compared` appears (proves
   velocity loop). 5. Then: Reddit/HN adapters, per-topic thresholds.
