# AI RADAR V1 — LIVE VALIDATION REPORT

Date: 2026-09-29 · Mode: everything runnable without secrets was executed live.
Secrets policy: values never printed, transmitted, or stored. Repo sweep: clean.

## Verdicts

| Check | Result | Evidence |
|---|---|---|
| Core pipeline | 🟢 PASS | dry-run + 3 real runs, 0 crashes |
| Collectors 6/6 | 🟢 PASS | 218 events, zero failures (1 transient GH rate-limit, graceful) |
| Telegram live send | ⚫ BLOCKED | no credentials in env; chat keys compromised — must rotate (see below) |
| Telegram mechanism | 🟢 PASS | format verified; no-creds→False; dup-proof proven (RUN1 sent=1, RUN2 sent=0) |
| Gemini live call | ⚫ BLOCKED | no key in env; chat key compromised — must rotate |
| Gemini mechanism | 🟢 PASS | bad-key→fallback in 0.7 s; retry+backoff; cap 12; `GEMINI_MODEL` honored |
| State persistence | 🟢 PASS | valid JSON, secret-free, 199 history snapshots, counts match |
| Duplicate protection | 🟢 PASS | proven end-to-end (stubbed transport) + state now committed |
| Cross-run history | 🟢 PASS | 177/243 events `history-compared` on live data |
| GitHub Actions | 🟡 PARTIAL | YAML valid, secrets-by-env, state persisted; execution needs push |
| Dashboard | 🟢 PASS | JS syntax clean, 240 real events mirrored, AR/EN present, 0 bad URLs |
| Security | 🟢 PASS | repo-wide sweep 0 hits; `.env` absent; state/dashboard JSON clean |

## LIVE COUNTS (dry-run, 5.9 s)

- GitHub: 56 · Hugging Face: 45 · arXiv: 57 · RSS: 30 · Press: 24 · YouTube: 6
- Total: 218 · After dedup: 218 · IMPORTANT+: 3 · Telegram alerts sent: 0
- Categories (15): MODEL 46, AGENT 40, NEWS 42, GITHUB 23, TOOL 14, … · free-test: 101/218

## PERFORMANCE

- Total dry-run 5.9 s (collect 5.8 s, process <0.1 s) · Gemini calls 0 · Telegram calls 0
- Retries: Gemini max 1 (+2 s) · Telegram 0 · collectors 0 (fail-fast per source)

## Fixes applied during validation (all safe, re-tested 20/20)

1. Stored events now refresh scores/analysis each run (was: stale forever) —
   this is what made `history-compared` visible (177 events).
2. `--limit-ai` CLI arg was parsed but ignored — now wired to Gemini cap.
3. Demo mode no longer writes `data/events.json` (preview → dashboard only);
   3 leftover demo fakes purged from production data.
4. README "real-time" → "near-real-time (~30 min polling)".

## What remains for YOU (only you can do these)

1. **Rotate the 3 chat-exposed secrets** (BotFather `/revoke`, delete PAT, new
   Gemini key) — then set GitHub Secrets `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`.
2. Push repo → enable Actions → manual run → check `Telegram alerts: N`.
3. On your own PC, run `python test_live.py` with your env keys for the
   one-message Telegram test + one-call Gemini test (script prints PASS/FAIL,
   never stores keys). Paste back only the PASS/FAIL lines.
4. Swap the placeholder YouTube channel for channels you follow.

`AI RADAR V1 LIVE VALIDATION COMPLETE`
