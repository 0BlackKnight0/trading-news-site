# backend/telegram_bot.py
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

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

async def send_digest():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping digest")
        return
    from telegram import Bot
    from database import get_market, get_news, get_telegram_chat_ids
    market = get_market()
    trading_news = get_news("trading")
    tech_news = get_news("tech")
    energy_news = get_news("energy")
    text = format_digest(market, trading_news, tech_news, energy_news)
    bot = Bot(token=token)
    chat_ids = get_telegram_chat_ids()
    for chat_id in chat_ids:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"Failed to send digest to {chat_id}: {e}")
    logger.info(f"Digest sent to {len(chat_ids)} users")

def create_application():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — bot polling disabled")
        return None
    from telegram.ext import Application, CommandHandler, ContextTypes
    from telegram import Update
    from database import save_telegram_user

    app = Application.builder().token(token).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        save_telegram_user(update.effective_chat.id)
        await update.message.reply_text(
            "✅ Registered! You'll receive the daily digest at 8 AM IST."
        )

    app.add_handler(CommandHandler("start", start))
    return app
