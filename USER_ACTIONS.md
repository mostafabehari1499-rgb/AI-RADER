# AI RADAR — USER ACTIONS

> I will never ask you to paste secrets. Only set them in the places below.
> The three keys shared in chat (Telegram token, GitHub PAT, Gemini key) must
> be treated as exposed — rotate them first (DO NOW).

## DO NOW (security + unblock)

- [ ] **Revoke the exposed Telegram token**: in Telegram, message @BotFather →
      `/revoke` for `@Al_rader_bot` (or `/deleteBot` + recreate). The old token
      must never be used or committed.
- [ ] **Delete the 1-hour GitHub PAT** (GitHub → Settings → Developer settings →
      Personal access tokens) and confirm expiry. Never paste PATs in chat.
- [ ] **Regenerate the Gemini key** (new key, restrict it), set it only as
      `GEMINI_API_KEY` (GitHub Secret or local `.env`, never in code).
- [ ] Get your numeric chat id: message your bot once, then open
      `https://api.telegram.org/bot<NEW_TOKEN>/getUpdates` (token in URL only,
      never in chat/code) and note `chat.id`. Send it to no one — put it in
      Secrets as `TELEGRAM_CHAT_ID`.

## DO ONCE (deploy)

- [ ] Repo Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
      `GEMINI_API_KEY`. Repo Variables (optional): `TELEGRAM_MIN_SCORE=75`,
      `GEMINI_MODEL=gemini-2.0-flash`, `RETENTION_DAYS=90`, `DAILY_DIGEST=false`.
- [ ] `git init && git add . && git commit -m "AI RADAR V1 audited" && push`
      to `mostafabehari1499-rgb/AI-RADER` (use a fresh credential, not the old PAT).
- [ ] Actions tab → enable → **Run workflow** manually → check logs show
      `Telegram alerts: N` and a data commit appears.
- [ ] **Safe Telegram test**: temporarily set variable `TELEGRAM_MIN_SCORE=60`,
      run once, confirm exactly one compact alert arrives, then restore 75.
- [ ] Settings → Pages → branch `main`, folder `/dashboard` → open the site.

## OPTIONAL (free upgrades)

- [ ] `GITHUB_TOKEN` secret (raises API limit 60→5000/hr).
- [ ] `YOUTUBE_API_KEY` (enables keyword search; channels work without it).
- [ ] Replace placeholder YouTube channel in `config/sources.yaml` with
      channels you follow; add blogs under `rss.sources`.

## LATER

- [ ] After ~10 scheduled runs: check an event shows
      `trend_basis: history-compared` (velocity loop alive).
- [ ] Reddit / Hacker News adapters, per-topic thresholds, benchmark tracking.
- [ ] Local runs: `run_demo.bat` (preview) · `run.bat` (real) ·
      `python -m unittest discover -s tests` (20 tests).
