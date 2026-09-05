# backend/routes/cron.py
"""Scheduled work, invoked by Vercel Cron.

Vercel sends `Authorization: Bearer $CRON_SECRET` when CRON_SECRET is set on
the project. Invocations are best-effort and may be duplicated, so everything
here is idempotent apart from the digest send.
"""
import logging
import os

from fastapi import APIRouter, Header, HTTPException

from aggregator_loop import run_market_refresh, run_news_refresh, run_signals_refresh
from telegram_bot import send_digest

router = APIRouter(prefix="/cron")
logger = logging.getLogger(__name__)


def _authorize(authorization: str | None):
    secret = os.environ.get("CRON_SECRET", "")
    if not secret:
        # Without a secret configured the endpoint stays closed rather than
        # letting anyone trigger a broadcast.
        raise HTTPException(status_code=401, detail="CRON_SECRET not configured")
    if authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/daily")
def daily(authorization: str | None = Header(default=None)):
    """Refresh both caches, then send the morning digest."""
    _authorize(authorization)

    result: dict = {"market": None, "news": None, "signals": None, "digest_sent": 0, "errors": {}}

    try:
        result["market"] = run_market_refresh()
    except Exception as e:
        logger.error(f"cron market refresh failed: {e}")
        result["errors"]["market"] = str(e)

    # Signals runs before news: it's what fetches each symbol's company name
    # (see pipeline._ensure_symbol_names), and news tagging needs that name
    # to match articles to a symbol. Running news first would tag nothing on
    # a database that has never had a signals refresh.
    try:
        result["signals"] = run_signals_refresh()
    except Exception as e:
        logger.error(f"cron signals refresh failed: {e}")
        result["errors"]["signals"] = str(e)

    try:
        result["news"] = run_news_refresh()
    except Exception as e:
        logger.error(f"cron news refresh failed: {e}")
        result["errors"]["news"] = str(e)

    try:
        result["digest_sent"] = send_digest()
    except Exception as e:
        logger.error(f"cron digest failed: {e}")
        result["errors"]["digest"] = str(e)

    return result
