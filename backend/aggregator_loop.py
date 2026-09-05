# backend/aggregator_loop.py
"""Cache refresh, driven on-read rather than by a background loop.

Vercel Hobby cron jobs only fire once per day, so the 15/30-minute refresh
cadence lives here instead: each read checks how old the cache is and
refreshes inline when it has gone stale.
"""
import logging
import time
from datetime import datetime, timezone

from aggregator.market import fetch_all as fetch_all_market
from aggregator.matching import aliases_for, match_symbols
from aggregator.news import fetch_all_news
from aggregator.ranking import apply_scores
from database import (
    get_all_watched_symbols,
    get_symbol_names,
    insert_news,
    mark_refreshed,
    prune_news,
    seconds_since_refresh,
    tag_news_symbol,
    upsert_market,
)
from pipeline import refresh_all


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

logger = logging.getLogger(__name__)

MARKET_TTL = 900    # 15 minutes
# News is the product's event-discovery layer.  Keep its cache no older than
# fifteen minutes whenever somebody is using the dashboard.
NEWS_TTL = 900      # 15 minutes
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


def _tag_matched_articles(items: list[dict]) -> None:
    """Tag each fetched article with any watchlist symbols it mentions."""
    names = get_symbol_names()
    if not names:
        return
    alias_map = {
        symbol: aliases for symbol, name in names.items()
        if (aliases := aliases_for(symbol, name))
    }
    if not alias_map:
        return
    for article in items:
        url = article.get("url")
        if not url:
            continue
        text = f"{article.get('title', '')} {article.get('summary') or ''}"
        for symbol in match_symbols(text, alias_map):
            tag_news_symbol(url, symbol)


def run_news_refresh():
    items = fetch_all_news()
    scored = apply_scores(items, _utc_now_iso())
    insert_news(scored)
    _tag_matched_articles(scored)
    prune_news()
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
