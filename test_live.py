"""Self-run live integration test. YOU run this on YOUR machine with YOUR keys.

PowerShell (paste YOUR OWN values only in your own terminal, never in chat):

  $env:TELEGRAM_BOT_TOKEN = "<paste-new-token-here>"
  $env:TELEGRAM_CHAT_ID = "<paste-chat-id-here>"
  $env:GEMINI_API_KEY = "<paste-new-key-here>"   # optional for part 2
  python test_live.py

Sends exactly ONE Telegram test message and makes at most ONE Gemini call.
Prints PASS/FAIL with sanitized errors only. Never writes secrets anywhere.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("== AI RADAR self live-test (1 telegram + max 1 gemini call) ==")

# ---- Part 1: Telegram ----
token = os.getenv("TELEGRAM_BOT_TOKEN", "")
chat = os.getenv("TELEGRAM_CHAT_ID", "")
if not token or not chat:
    print("Telegram LIVE: BLOCKED (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing)")
else:
    from engine.notifications import telegram as tg
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = (f"AI RADAR LIVE TEST\n{stamp}\nEnvironment: local self-test\n"
            f"Result: bot reachable, chat writable. No batch alerts sent.")
    try:
        ok = tg.send_message(token, chat, body.replace("<", "&lt;"))
        print("Telegram LIVE:", "PASS" if ok else "FAIL (api-rejected-or-network)")
    except Exception as e:
        print(f"Telegram LIVE: FAIL ({type(e).__name__})")

# ---- Part 2: Gemini (single harmless call) ----
key = os.getenv("GEMINI_API_KEY", "")
if not key:
    print("Gemini LIVE: BLOCKED (GEMINI_API_KEY missing)")
else:
    from engine.config import load_config
    from engine.processors.normalize import make_event
    from engine.processors.summarize import _gemini
    cfg = load_config()
    model = cfg.get("gemini_model", "gemini-2.0-flash")
    ev = make_event("Self-test event", "https://example.com/selftest",
                    "SelfTest", "rss", "Connectivity probe. No real claims.")
    try:
        res = _gemini(ev, key, model)
        if res and res.get("summary_en"):
            print(f"Gemini LIVE: PASS (model={res.get('ai_model')})")
        else:
            print("Gemini LIVE: FAIL (empty-or-unparsed-response, fallback-ok)")
    except Exception as e:
        print(f"Gemini LIVE: FAIL ({type(e).__name__})")
print("done.")
