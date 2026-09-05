# backend/aggregator_loop.py
"""Cache refresh, driven on-read rather than by a background loop.

Vercel Hobby cron jobs only fire once per day, so the 15/30-minute refresh
cadence lives here instead: each read checks how old the cache is and
refreshes inline when it has gone stale.
"""
import logging
import time

from aggregator.market import fetch_all as fetch_all_market
from aggregator.news import fetch_all_news
from database import (
    get_all_watched_symbols,
    insert_news,
    mark_refreshed,
    seconds_since_refresh,
    upsert_market,
)
from pipeline import refresh_all

logger = logging.getLogger(__name__)

MARKET_TTL = 900    # 15 minutes
NEWS_TTL = 1800     # 30 minutes
SIGNALS_TTL = 900   # 15 minutes

# Per-instance memo. Warm invocations skip the staleness query entirely, and
# it caps the damage to one refresh per TTL if refresh_meta is unavailable.
_local_refresh: dict[str, float] = {}


def _is_stale(key: str, ttl: int) -> bool:
    last_local = _local_refresh.get(key)
    if last_local is not None and (time.monotonic() - last_local) < ttl:
        return False
    age = seconds_since_refresh(key)
    return age is None or age >= ttl


def _mark(key: str):
    _local_refresh[key] = time.monotonic()
    mark_refreshed(key)


def run_market_refresh():
    items = fetch_all_market()
    for item in items:
        upsert_market(item["symbol"], item["price"], item["change_pct"], item["category"])
    if items:
        _mark("market")
    logger.info(f"Market refreshed: {len(items)} symbols")
    return len(items)


def run_news_refresh():
    items = fetch_all_news()
    insert_news(items)
    if items:
        _mark("news")
    logger.info(f"News refreshed: {len(items)} articles")
    return len(items)


def run_signals_refresh():
    result = refresh_all(get_all_watched_symbols())
    if result["symbols"]:
        _mark("signals")
    logger.info(f"Signals refreshed: {result['events']} events")
    return result["events"]


def refresh_market_if_stale() -> bool:
    """Refresh market data when the cache has expired. Never raises."""
    if not _is_stale("market", MARKET_TTL):
        return False
    try:
        run_market_refresh()
        return True
    except Exception as e:
        logger.error(f"Market refresh failed: {e}")
        return False


def refresh_news_if_stale() -> bool:
    """Refresh news when the cache has expired. Never raises."""
    if not _is_stale("news", NEWS_TTL):
        return False
    try:
        run_news_refresh()
        return True
    except Exception as e:
        logger.error(f"News refresh failed: {e}")
        return False


def refresh_signals_if_stale() -> bool:
    """Refresh signals when the cache has expired. Never raises."""
    if not _is_stale("signals", SIGNALS_TTL):
        return False
    try:
        run_signals_refresh()
        return True
    except Exception as e:
        logger.error(f"Signals refresh failed: {e}")
        return False
