# backend/aggregator/news.py
import os
import re
import html
import feedparser
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

RSS_FEEDS = {
    "trading": [
        ("https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "Economic Times"),
        ("https://www.moneycontrol.com/rss/business.xml", "Moneycontrol"),
        ("https://feeds.reuters.com/reuters/businessNews", "Reuters Markets"),
    ],
    "tech": [
        ("https://techcrunch.com/category/artificial-intelligence/feed/", "TechCrunch AI"),
        ("https://venturebeat.com/category/ai/feed/", "VentureBeat AI"),
        ("https://www.technologyreview.com/feed/", "MIT Tech Review"),
        ("https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "The Verge AI"),
        ("https://www.scmp.com/rss/4/feed", "SCMP Tech"),
    ],
    "energy": [
        ("https://feeds.reuters.com/reuters/energyNews", "Reuters Energy"),
        ("https://oilprice.com/rss/main", "OilPrice.com"),
        ("https://cleantechnica.com/feed/", "CleanTechnica"),
    ],
}

NEWSAPI_QUERIES = {
    "trading": (
        "stock market OR NSE OR BSE OR Sensex OR Nifty OR RBI OR SEBI"
        " OR earnings OR IPO OR FII OR hedge fund OR equity market"
    ),
    "tech": (
        "artificial intelligence OR AI model OR LLM OR ChatGPT OR Claude AI"
        " OR Gemini OR DeepSeek OR China AI OR AI agent OR OpenAI OR Anthropic"
        " OR Nvidia AI OR Baidu AI OR Alibaba AI OR Qwen OR Grok AI OR Llama"
        " OR AI startup OR foundation model"
    ),
    "energy": (
        "oil price OR crude oil OR natural gas OR OPEC OR renewable energy"
        " OR solar power OR wind power OR gigawatt OR energy market OR LNG"
        " OR battery storage OR nuclear power plant"
    ),
}

NEWS_PER_FEED = 10
HTTP_TIMEOUT = 10
MAX_WORKERS = 8
FEED_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TradingNewsBot/1.0)"}

_TRADING_BLOCK = [
    "biopic", " actor ", " actress ", "film release", "movie release",
    "delivers baby", "pregnant woman", "operation matrishakti",
    "takes oath", "sworn in as", "chief minister",
    "mother's day", "mothers' day", "rescue operation",
    " ipl ", "cricket match", "football score",
    "wedding ceremony",
]

_TRADING_ALLOW = [
    "market", "stock", "share", "nse", "bse", "sensex", "nifty",
    "rupee", "rbi", "sebi", "ipo", "trading", "invest",
    "equity", "bond", "fund", "etf", "commodity", "gold", "silver",
    "oil", "crude", "forex", "currency", "inflation", "gdp",
    "earnings", "profit", "revenue", "quarterly", "result",
    "buyback", "dividend", "acquisition", "merger", "listing",
    "nasdaq", "dow jones", "s&p", "rate", "rally", "crash",
    "surge", "fell", "dropped", "gains", "loss", "bull", "bear",
    "mutual fund", "smallcap", "midcap", "largecap",
    "q1 ", "q2 ", "q3 ", "q4 ", "fy2", "fiscal",
]


def _clean_html(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text or '')
    text = html.unescape(text)
    return ' '.join(text.split())[:240]


def _is_trading_relevant(title: str) -> bool:
    lower = title.lower()
    for term in _TRADING_BLOCK:
        if term in lower:
            return False
    for term in _TRADING_ALLOW:
        if term in lower:
            return True
    return False


def parse_rss(url: str, category: str, source: str) -> list[dict]:
    try:
        # Fetch with requests rather than letting feedparser open the URL —
        # feedparser has no timeout, and a hung feed would stall the request.
        resp = requests.get(url, headers=FEED_HEADERS, timeout=HTTP_TIMEOUT)
        feed = feedparser.parse(resp.content)
        items = []
        for entry in feed.entries[:NEWS_PER_FEED]:
            published_at = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
            title = getattr(entry, "title", "") or ""
            if not title:
                continue
            if category == "trading" and not _is_trading_relevant(title):
                continue
            url_ = getattr(entry, "link", "") or ""
            raw = (getattr(entry, "summary", "") or getattr(entry, "description", "") or "")
            summary = _clean_html(raw) or None
            items.append({
                "title": title,
                "url": url_,
                "source": source,
                "category": category,
                "published_at": published_at,
                "summary": summary,
            })
        return items
    except Exception:
        return []


def fetch_newsapi(category: str) -> list[dict]:
    key = os.environ.get("NEWSAPI_KEY", "")
    if not key:
        return []
    query = NEWSAPI_QUERIES.get(category, "")
    url = (
        f"https://newsapi.org/v2/everything?q={query}"
        f"&language=en&sortBy=publishedAt&pageSize=10&apiKey={key}"
    )
    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT)
        articles = resp.json().get("articles", [])
        results = []
        for a in articles:
            title = a.get("title", "") or ""
            if not title or "[Removed]" in title:
                continue
            if category == "trading" and not _is_trading_relevant(title):
                continue
            desc = _clean_html(a.get("description", "") or "") or None
            results.append({
                "title": title,
                "url": a["url"],
                "source": a["source"]["name"],
                "category": category,
                "published_at": a.get("publishedAt"),
                "summary": desc,
            })
        return results
    except Exception:
        return []


def _dedupe(items: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique


def _gather(tasks: list) -> list[dict]:
    """Run fetch callables concurrently and flatten their results.

    Feeds are independent and I/O bound, so serial fetching would make the
    on-read refresh far slower than the request budget allows.
    """
    if not tasks:
        return []
    items: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(tasks))) as pool:
        for result in pool.map(lambda fn: fn(), tasks):
            items.extend(result)
    return items


def fetch_news(category: str) -> list[dict]:
    tasks = [
        (lambda u=url, s=source: parse_rss(u, category, s))
        for url, source in RSS_FEEDS.get(category, [])
    ]
    tasks.append(lambda: fetch_newsapi(category))
    return _dedupe(_gather(tasks))


def fetch_all_news() -> list[dict]:
    categories = ["trading", "tech", "energy"]
    tasks = []
    for category in categories:
        tasks.extend(
            (lambda u=url, s=source, c=category: parse_rss(u, c, s))
            for url, source in RSS_FEEDS.get(category, [])
        )
        tasks.append(lambda c=category: fetch_newsapi(c))
    return _dedupe(_gather(tasks))
