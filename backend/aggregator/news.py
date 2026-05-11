# backend/aggregator/news.py
import os
import feedparser
import requests
from datetime import datetime, timezone

RSS_FEEDS = {
    "trading": [
        ("https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "Economic Times"),
        ("https://www.moneycontrol.com/rss/business.xml", "Moneycontrol"),
        ("https://feeds.feedburner.com/ndtvprofit-latest", "NDTV Profit"),
    ],
    "tech": [
        ("https://techcrunch.com/feed/", "TechCrunch"),
        ("https://www.theverge.com/rss/index.xml", "The Verge"),
    ],
    "energy": [
        ("https://feeds.reuters.com/reuters/businessNews", "Reuters"),
        ("https://cleantechnica.com/feed/", "CleanTechnica"),
    ],
}

NEWSAPI_QUERIES = {
    "trading": "stock market OR NSE OR BSE OR RBI OR SEBI OR trading",
    "tech": "Nvidia AI OR Anthropic OR OpenAI OR artificial intelligence OR LLM",
    "energy": "renewable energy OR solar OR wind power OR space energy OR gigawatt",
}

NEWS_PER_FEED = 10
HTTP_TIMEOUT = 10


def parse_rss(url: str, category: str, source: str) -> list[dict]:
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:NEWS_PER_FEED]:
            published_at = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
            title = getattr(entry, "title", "") or entry.get("title", "")
            url_ = getattr(entry, "link", "") or entry.get("link", "")
            items.append({
                "title": title,
                "url": url_,
                "source": source,
                "category": category,
                "published_at": published_at,
            })
        return items
    except Exception:
        return []


def fetch_newsapi(category: str) -> list[dict]:
    key = os.environ.get("NEWSAPI_KEY", "")
    if not key:
        return []
    query = NEWSAPI_QUERIES.get(category, "")
    url = f"https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&pageSize=10&apiKey={key}"
    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT)
        articles = resp.json().get("articles", [])
        return [
            {
                "title": a["title"],
                "url": a["url"],
                "source": a["source"]["name"],
                "category": category,
                "published_at": a.get("publishedAt"),
            }
            for a in articles
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]
    except Exception:
        return []


def fetch_news(category: str) -> list[dict]:
    items = []
    for url, source in RSS_FEEDS.get(category, []):
        items.extend(parse_rss(url, category, source))
    items.extend(fetch_newsapi(category))
    seen = set()
    unique = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique


def fetch_all_news() -> list[dict]:
    all_items = []
    for category in ["trading", "tech", "energy"]:
        all_items.extend(fetch_news(category))
    return all_items
