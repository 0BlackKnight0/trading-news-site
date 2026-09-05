# backend/aggregator/news.py
import os
import re
import html
import feedparser
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

# Four feeds were removed on 2026-09-05 after being verified dead or blocking:
# both feeds.reuters.com endpoints (domain no longer resolves), Moneycontrol
# (403 against our User-Agent) and VentureBeat (429). Curating replacements is
# a research task, not an engineering one — see the spec's "out of scope".
RSS_FEEDS = {
    "trading": [
        ("https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "Economic Times"),
    ],
    "tech": [
        ("https://techcrunch.com/category/artificial-intelligence/feed/", "TechCrunch AI"),
        ("https://www.technologyreview.com/feed/", "MIT Tech Review"),
        ("https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "The Verge AI"),
        ("https://www.scmp.com/rss/4/feed", "SCMP Tech"),
    ],
    "energy": [
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


_TECH_BLOCK = [
    "comic", "marvel", "dc studios", "box office", "trailer for",
    "casting", "celebrity", "film release", "movie release",
    "tv series", "episode", "season finale", "horoscope",
]

_TECH_ALLOW = [
    "ai", "artificial intelligence", "llm", "language model", "openai",
    "anthropic", "chatgpt", "claude", "gemini", "deepseek", "qwen", "llama",
    "mistral", "copilot", "nvidia", "gpu", "chip", "semiconductor",
    "datacenter", "data center", "machine learning", "neural", "transformer",
    "inference", "training run", "agent", "robotics", "quantum", "cloud",
    "software", "startup", "funding round", "acquisition", "algorithm",
    "compute", "silicon", "model release",
]

_ENERGY_BLOCK = [
    "auction", "for sale", "classic car", "bring a trailer",
    "horoscope", "recipe", "celebrity", "film release", "box office",
]

_ENERGY_ALLOW = [
    "oil", "crude", "brent", "wti", "opec", "natural gas", "lng", "pipeline",
    "refinery", "barrel", "energy", "power grid", "electricity", "megawatt",
    "gigawatt", "solar", "wind farm", "nuclear", "reactor", "battery",
    "storage", "renewable", "coal", "utility", "emissions", "carbon",
    "hydrogen", "drilling", "fuel", "grid",
]

# category -> (block list, allow list). A category absent from this map is
# unfiltered: better to let news through than to silently drop a whole
# category because someone added it without lists.
_CATEGORY_FILTERS = {
    "trading": (_TRADING_BLOCK, _TRADING_ALLOW),
    "tech": (_TECH_BLOCK, _TECH_ALLOW),
    "energy": (_ENERGY_BLOCK, _ENERGY_ALLOW),
}

# Sources NewsAPI keeps surfacing that never carry market news. Matched on the
# article's source NAME, not its url, because that is what the API returns.
_SOURCE_DENYLIST = [
    "naturalnews", "wattsupwiththat", "bringatrailer", "dailymail",
    "comic book movie", "deadline", "newsonjapan",
]


def _is_denied_source(source: str) -> bool:
    lower = (source or "").lower()
    return any(bad in lower for bad in _SOURCE_DENYLIST)


def _is_relevant(title: str, category: str) -> bool:
    """Keyword relevance for one category.

    Previously this existed for `trading` only, which is why a car auction
    site and an entertainment blog reached the energy and tech feeds in
    production — NewsAPI keyword-matches across ~150k sources and does exactly
    what a broad query asks.
    """
    filters = _CATEGORY_FILTERS.get(category)
    if not filters:
        return True
    block, allow = filters
    lower = title.lower()
    for term in block:
        if term in lower:
            return False
    for term in allow:
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
            if not _is_relevant(title, category):
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
            source_name = a["source"]["name"]
            if _is_denied_source(source_name):
                continue
            if not _is_relevant(title, category):
                continue
            desc = _clean_html(a.get("description", "") or "") or None
            results.append({
                "title": title,
                "url": a["url"],
                "source": source_name,
                "category": category,
                "published_at": a.get("publishedAt"),
                "summary": desc,
            })
        return results
    except Exception:
        return []


def _dedupe(items: list[dict]) -> list[dict]:
    """Collapse duplicates by url — the database's uniqueness contract.

    A falsy url (missing/empty) can't be used to tell items apart, so such
    items are kept as-is rather than collapsing into one another.
    """
    seen = set()
    unique = []
    for item in items:
        url = item.get("url")
        if not url:
            unique.append(item)
            continue
        if url not in seen:
            seen.add(url)
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


# Yahoo's search endpoint resolves a ticker to its own news. Matching
# headlines to symbols ourselves would be fragile — "TCS" appears inside
# unrelated words and "INFY" never appears in prose at all — so entity
# resolution is Yahoo's problem. routes/ticker.py already uses this endpoint
# successfully in production.
SYMBOL_NEWS_URL = "https://query2.finance.yahoo.com/v1/finance/search"
SYMBOL_NEWS_COUNT = 8
SYMBOL_NEWS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


def fetch_symbol_news(symbol: str) -> list[dict]:
    """Recent news for one ticker. Returns [] on any failure."""
    try:
        resp = requests.get(
            SYMBOL_NEWS_URL,
            params={"q": symbol, "newsCount": SYMBOL_NEWS_COUNT, "quotesCount": 0},
            headers=SYMBOL_NEWS_HEADERS,
            timeout=HTTP_TIMEOUT,
        )
        entries = resp.json().get("news") or []
    except Exception:
        return []

    items = []
    for entry in entries:
        title = entry.get("title") or ""
        if not title:
            continue
        source = entry.get("publisher") or ""
        if _is_denied_source(source):
            continue
        ts = entry.get("providerPublishTime")
        published_at = (
            datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None
        )
        items.append({
            "title": title,
            "url": entry.get("link") or "",
            "source": source,
            "category": None,       # symbol rows carry no category
            "published_at": published_at,
            "summary": _clean_html(entry.get("summary") or "") or None,
            "symbol": symbol,
        })
    return items


def fetch_all_symbol_news(symbols: list[str]) -> list[dict]:
    """Fetch every symbol concurrently. One dead symbol never stops the rest."""
    if not symbols:
        return []

    def one(symbol: str) -> list[dict]:
        try:
            return fetch_symbol_news(symbol)
        except Exception:
            return []

    items: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(symbols))) as pool:
        for result in pool.map(one, symbols):
            items.extend(result)
    return _dedupe(items)
