# backend/routes/news.py
from fastapi import APIRouter, Query

from aggregator_loop import refresh_news_if_stale
from database import get_news

router = APIRouter()

@router.get("/news")
def news(category: str = Query(default="trading", enum=["trading", "tech", "energy"])):
    # No background worker on serverless — the read refreshes stale data.
    refresh_news_if_stale()
    return get_news(category)
