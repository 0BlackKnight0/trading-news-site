# backend/telegram_bot.py
"""Telegram integration.

Serverless functions cannot hold a long-lived polling connection, so updates
arrive via webhook (see routes/telegram.py) and outbound messages go straight
to the Bot HTTP API — no python-telegram-bot dependency.
"""
import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}/{method}"
HTTP_TIMEOUT = 10


def _token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def _call(method: str, payload: dict) -> bool:
    token = _token()
    if not token:
        return False
    try:
        resp = requests.post(
            API_BASE.format(token=token, method=method),
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        if not resp.ok:
            logger.error(f"Telegram {method} failed: {resp.status_code} {resp.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"Telegram {method} error: {e}")
        return False


def send_message(chat_id: int, text: str) -> bool:
    return _call("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })


def _arrow(change_pct: float) -> str:
    return "▲" if change_pct >= 0 else "▼"


def _signed(change_pct: float) -> str:
    sign = "+" if change_pct >= 0 else ""
    return f"{sign}{change_pct:.2f}%"


def format_digest(
    market: list[dict],
    trading_news: list[dict],
    tech_news: list[dict],
    energy_news: list[dict],
) -> str:
    date_str = datetime.now().strftime("%a %d %b, %Y")
    lines = [f"🌅 *Morning Digest — {date_str}, 8:00 AM IST*\n"]

    lines.append("📈 *MARKETS*")
    india = [m for m in market if m["category"] == "india"]
    crypto = [m for m in market if m["category"] == "crypto"][:4]
    forex = [m for m in market if m["category"] == "forex"][:3]
    for m in india + crypto + forex:
        lines.append(
            f"`{m['symbol']}` {m['price']:,.2f} {_arrow(m['change_pct'])} {_signed(m['change_pct'])}"
        )

    lines.append("\n🏦 *TRADING NEWS*")
    for item in trading_news[:3]:
        lines.append(f"• [{item['title']}]({item['url']})")

    lines.append("\n🤖 *AI & TECH*")
    for item in tech_news[:3]:
        lines.append(f"• [{item['title']}]({item['url']})")

    lines.append("\n⚡ *ENERGY & SPACE*")
    for item in energy_news[:3]:
        lines.append(f"• [{item['title']}]({item['url']})")

    return "\n".join(lines)


def send_digest() -> int:
    """Send the morning digest to every registered chat. Returns send count."""
    if not _token():
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping digest")
        return 0

    from database import get_market, get_news, get_telegram_chat_ids

    text = format_digest(
        get_market(),
        get_news("trading"),
        get_news("tech"),
        get_news("energy"),
    )

    sent = 0
    for chat_id in get_telegram_chat_ids():
        if send_message(chat_id, text):
            sent += 1
    logger.info(f"Digest sent to {sent} users")
    return sent


def handle_update(update: dict) -> None:
    """Process one webhook update. Only /start is supported."""
    message = update.get("message") or update.get("channel_post") or {}
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return

    # Telegram sends "/start" or "/start@botname" in groups.
    command = text.split()[0].split("@")[0].lower()
    if command != "/start":
        return

    from database import save_telegram_user

    save_telegram_user(chat_id)
    send_message(
        chat_id,
        "✅ Registered! You'll receive the daily digest at 8 AM IST.",
    )
