# backend/routes/news.py
"""Market news, and news about what the caller actually holds.

/news is anonymous: market news is the same for everyone. /news/symbols is
per-user, because it is scoped to that user's watchlist.
"""
from fastapi import APIRouter, Depends, Query

from aggregator_loop import refresh_news_if_stale
from database import (
    count_news_since,
    get_news,
    get_news_last_seen,
    get_symbol_news,
    get_watchlist,
    set_news_last_seen,
)
from identity import current_user

router = APIRouter()

SYMBOL_NEWS_LIMIT = 30


@router.get("/news")
def news(category: str = Query(default="trading", enum=["trading", "tech", "energy"])):
    # No background worker on serverless — the read refreshes stale data.
    refresh_news_if_stale()
    return get_news(category)


@router.get("/news/symbols")
def symbol_news(user: dict = Depends(current_user)):
    refresh_news_if_stale()
    symbols = [row["symbol"] for row in get_watchlist(user["id"])]
    baseline = get_news_last_seen(user["id"])
    return {
        "items": get_symbol_news(symbols, limit=SYMBOL_NEWS_LIMIT),
        "unread_count": count_news_since(symbols, baseline),
        "news_last_seen_at": baseline,
    }


@router.post("/news/seen")
def news_seen(user: dict = Depends(current_user)):
    """Catch up on news only — the Changes baseline is untouched."""
    return {"news_last_seen_at": set_news_last_seen(user["id"])}
