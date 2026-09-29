# ⚡ AI RADAR — Discover → Understand → Test → Create

Your personal near-real-time AI intelligence system (scheduled polling, ~30 min). It discovers AI releases across
GitHub, Hugging Face, arXiv, YouTube, RSS and official blogs, dedupes them into
ONE event, scores importance + trend, finds **free** ways to test, drafts
bilingual summaries + content ideas, pings you on Telegram, and publishes a
mobile-friendly static dashboard.

**100% free V1:** Python + JSON + static HTML. GitHub Actions = backend,
GitHub Pages = dashboard. No VPS, Docker, or database server.

---

## 1. What AI RADAR is

Every important event answers: **WHAT? WHY? HOW IMPORTANT? CAN I TEST IT?
WHERE FOR FREE? WHAT HARDWARE? WHAT VIDEO CAN I MAKE?**

```
INTERNET → COLLECTORS → NORMALIZE → DEDUP → CLASSIFY → SCORE → AI ANALYSIS
        → FREE-TEST FINDER → CONTENT ANGLES → TELEGRAM + DASHBOARD
```

## 2. Architecture

| Layer | Where | Notes |
|---|---|---|
| Collectors | `engine/collectors/` | GitHub, HF, arXiv, YouTube (RSS, no key), RSS, official blogs |
| Processors | `engine/processors/` | normalize, deduplicate, classify, score, summarize, experiment_finder |
| Storage | `data/*.json` | events, trending, models, sources, state — no DB |
| Notify | `engine/notifications/telegram.py` | Bot API, threshold-gated |
| UI | `dashboard/` | static HTML/CSS/JS, `localStorage` saves |
| Schedule | `.github/workflows/radar.yml` | every 30 min, commits JSON |

## 3. Installation

```bash
git clone <your-repo-url> ai-radar
cd ai-radar
pip install -r requirements.txt
```

Windows: double-click `run_demo.bat` (demo) or `run.bat` (real run).
Linux/macOS: `bash run.sh` or `bash run.sh --demo`.

## 4. GitHub setup

1. Create a repo, push this project.
2. Actions tab → enable workflows.

## 5. Telegram bot creation (2 min)

1. Open Telegram, chat with **@BotFather** → `/newbot` → copy the token.
2. Message your new bot once (any text).
3. Get your chat id: open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser, find `"chat":{"id":12345}`.
4. Keep both values for the next step.

## 6. GitHub Secrets

Repo → **Settings → Secrets and variables → Actions**:

- Secret `TELEGRAM_BOT_TOKEN` = token from BotFather
- Secret `TELEGRAM_CHAT_ID` = your numeric chat id
- Secret `GEMINI_API_KEY` = (optional, see below)

Optional variables (**Settings → Variables**): `TELEGRAM_MIN_SCORE` (default `75`), `DAILY_DIGEST` (`true`/`false`).

## 7. Gemini configuration (optional, free tier)

1. Go to Google AI Studio, create an API key.
2. Add it as secret `GEMINI_API_KEY`.
3. Without it the pipeline still works — deterministic bilingual templates are used and clearly labelled.

## 8. GitHub Actions

Workflow file: `.github/workflows/radar.yml` (every 30 min + manual dispatch).
Change schedule: edit the `cron: "*/30 * * * *"` line (e.g. `"*/15 * * * *"`).

## 9. GitHub Pages

1. Repo → **Settings → Pages** → Source: **Deploy from a branch**, Branch: `main`, Folder: `/dashboard`.
2. Open `https://<you>.github.io/<repo>/` — the workflow mirrors `data/*.json` into `dashboard/data/` each run.
3. Local preview: `python -m engine.main --demo`, then open `dashboard/index.html`.

## 10. Adding RSS sources

Edit `config/sources.yaml` → `rss.sources`, append:

```yaml
- name: "My AI Blog"
  url: "https://example.com/feed.xml"
  category: "research"
  enabled: true
  priority: medium
```

## 11. Adding YouTube channels

Find the channel ID (page source → `channelId`, or URL `/channel/UC...`), then edit `config/sources.yaml`:

```yaml
- name: "Some AI Channel"
  channel_id: "UCxxxxxxxxxxxxxxxx"
  enabled: true
```

No API key needed (RSS). Optionally set `YOUTUBE_API_KEY` secret for search terms.

## 12. Changing alert threshold

Set env `TELEGRAM_MIN_SCORE=75` (BREAKING ≥90, HIGH ≥75, IMPORTANT ≥60 auto-derived).
In Actions: repo Variables → `TELEGRAM_MIN_SCORE`. Locally: `.env` file or env var.

## 13. Running locally

```bash
pip install -r requirements.txt
python -m engine.main --demo      # fake data, no keys, no network
python -m engine.main --dry-run   # real collection, no Telegram, no state writes
python -m engine.main             # full run
python -m unittest discover -s tests
```

## 14. Demo / dry-run modes

- `--demo`: 5 fake events exercising dedup, scoring, Telegram formatting, dashboard data.
- `--dry-run`: live collectors, full analysis, but never sends Telegram.

## 15. Troubleshooting

| Symptom | Fix |
|---|---|
| `rate-limited` in GitHub log | Add `GITHUB_TOKEN` secret (raises limit 60→5000/hr) |
| RSS `parse failed` | Feed URL moved; disable it or replace URL in `sources.yaml` |
| No Telegram | Check secrets names; message the bot first; threshold may filter (lower `TELEGRAM_MIN_SCORE` to 60 to test) |
| Empty dashboard | Run `--demo` once; check `data/events.json` exists |
| Workflow push fails | Ensure `permissions: contents: write` (already in yml) |

## Known limitations (V1)

- Trend velocity uses same-run signals (no cross-run history yet beyond notified ids).
- YouTube without API key tracks configured channels only, not global search.
- Hardware tiers are rough estimates, always labelled `estimated`.
- AI calls capped at 12/run to stay on free tiers.
