# backend/aggregator_loop.py
import logging
from aggregator.market import fetch_all as fetch_all_market
from aggregator.news import fetch_all_news
from database import upsert_market, insert_news

logger = logging.getLogger(__name__)

def run_market_refresh():
    items = fetch_all_market()
    for item in items:
        upsert_market(item["symbol"], item["price"], item["change_pct"], item["category"])
    logger.info(f"Market refreshed: {len(items)} symbols")

def run_news_refresh():
    items = fetch_all_news()
    insert_news(items)
    logger.info(f"News refreshed: {len(items)} articles")
