"""Telegram notifications: alert formatting + Bot API sender.

Secrets come ONLY from env (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID).
format_alert() is pure and unit-tested; send_*() do network I/O.
"""
from __future__ import annotations

from typing import Dict, List

import requests

API_TMPL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LEN = 3900


def _esc(text: str) -> str:
    return (text or "").replace("<", "&lt;").replace(">", "&gt;").replace("&lt;", "&lt;")


def format_alert(ev: Dict) -> str:
    level = ev.get("importance_level", "?")
    ai = ev.get("ai", {}) or {}
    exp = ev.get("experiment", {}) or {}
    emoji = {"BREAKING": "🚨", "HIGH": "🔥", "IMPORTANT": "⚡"}.get(level, "ℹ️")
    test_lines = []
    for o in (exp.get("options", []) or [])[:3]:
        test_lines.append(f"🟢 {o['name']}")
    if not test_lines:
        test_lines.append("🔴 " + (exp.get("note") or "No verified free test found"))
    formats = ", ".join((ai.get("content_formats") or [])[:3]) or ev.get("category", "")
    msg = (
        f"{emoji} <b>AI RADAR — {level}</b>\n\n"
        f"🤖 <b>{_esc(ev.get('title','')[:160])}</b>\n"
        f"{_esc(ev.get('category',''))} · {_esc(ev.get('source',''))}\n"
        f"━━━━━━━━━━━━\n"
        f"🧠 <b>WHAT HAPPENED</b>\n{_esc((ai.get('summary_ar') or ev.get('description','')[:300])[:500])}\n"
        f"━━━━━━━━━━━━\n"
        f"🔥 <b>WHY IT MATTERS</b>\n{_esc((ai.get('why') or '; '.join(ev.get('importance_reasons', [])[:2]))[:400])}\n"
        f"━━━━━━━━━━━━\n"
        f"🧪 <b>FREE TEST</b>\n" + "\n".join(test_lines) + "\n"
        f"━━━━━━━━━━━━\n"
        f"🎬 <b>CONTENT</b>\n{_esc(formats)}\n"
        f"━━━━━━━━━━━━\n"
        f"📊 IMPORTANCE <b>{ev.get('importance_score',0)}/100</b> · 📈 {ev.get('trend_status','')}\n"
        f"🔗 <a href=\"{_esc(ev.get('url',''))}\">SOURCE</a>"
    )
    return msg[:MAX_LEN]


def format_digest(events: List[Dict]) -> str:
    top = sorted(events, key=lambda e: e.get("importance_score", 0), reverse=True)[:10]
    lines = ["⚡ <b>AI RADAR DAILY</b>", f"{len(events)} important discoveries", ""]
    for i, ev in enumerate(top, 1):
        lines.append(f"{i}. <a href=\"{ev.get('url','')}\">{_esc(ev.get('title','')[:90])}</a> ({ev.get('importance_score',0)})")
    lines += ["", "Open the dashboard for details."]
    return "\n".join(lines)[:MAX_LEN]


def send_message(token: str, chat_id: str, html: str, timeout: int = 20) -> bool:
    if not token or not chat_id:
        return False
    try:
        r = requests.post(API_TMPL.format(token=token),
                          json={"chat_id": chat_id, "text": html,
                                "parse_mode": "HTML", "disable_web_page_preview": False},
                          timeout=timeout)
        return r.status_code == 200 and (r.json().get("ok") is True)
    except Exception:
        return False


def diagnose(token: str, chat_id: str, timeout: int = 15) -> str:
    """Safe diagnosis: validates token via getMe, then reports the exact
    failure class. NEVER includes secret values in the returned string."""
    if not token or not chat_id:
        return "diagnosis: missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=timeout)
        data = r.json() if r.status_code == 200 else {}
        if not data.get("ok"):
            return f"diagnosis: token rejected (http {r.status_code}) — update TELEGRAM_BOT_TOKEN"
        name = ((data.get("result") or {}).get("username") or "?")
        # token ok -> probe delivery with an empty-ish harmless ping is avoided;
        # report chat-side verdict from a dry send attempt is done by caller.
        return (f"diagnosis: token OK (bot @{name}); "
                "send failed -> TELEGRAM_CHAT_ID is wrong or bot not started (send it /start)")
    except Exception as e:
        return f"diagnosis: network error ({type(e).__name__})"


def send_alerts(events: List[Dict], token: str, chat_id: str, min_score: int = 75):
    """Send alerts for events >= min_score. Returns (sent, failed)."""
    sent = failed = 0
    for ev in sorted(events, key=lambda e: e.get("importance_score", 0), reverse=True):
        if int(ev.get("importance_score", 0) or 0) < min_score:
            continue
        if send_message(token, chat_id, format_alert(ev)):
            sent += 1
            ev["notified"] = True
        else:
            failed += 1
    return sent, failed
