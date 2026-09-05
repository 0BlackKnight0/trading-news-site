# backend/tests/test_news.py
from unittest.mock import patch, MagicMock
from aggregator.news import NEWSAPI_QUERIES, RSS_FEEDS, _dedupe, fetch_news, parse_rss

def test_parse_rss_returns_list_of_dicts():
    mock_feed = MagicMock()
    mock_entry = MagicMock()
    mock_entry.title = "Nifty falls 200 points as market sells off"
    mock_entry.link = "http://test.com"
    mock_entry.published_parsed = (2026, 5, 11, 8, 0, 0, 0, 0, 0)
    mock_entry.summary = ""
    mock_entry.description = ""
    mock_feed.entries = [mock_entry]
    with patch("aggregator.news.requests.get", return_value=MagicMock(content=b"<rss/>")):
        with patch("aggregator.news.feedparser.parse", return_value=mock_feed):
            result = parse_rss("http://fake-rss.com", "trading", "TestSource")
    assert len(result) == 1
    assert result[0]["title"] == "Nifty falls 200 points as market sells off"
    assert result[0]["category"] == "trading"
    assert result[0]["source"] == "TestSource"


def test_parse_rss_survives_a_dead_feed():
    with patch("aggregator.news.requests.get", side_effect=TimeoutError("no response")):
        assert parse_rss("http://dead-feed.com", "trading", "TestSource") == []

def test_fetch_news_returns_items_for_category():
    # "markets" is the current name for what used to be "trading" — the
    # category rename in a886bc8 dropped RSS_FEEDS["trading"] entirely, so a
    # mocked parse_rss is never even reached for the old name.
    mock_items = [{"title": "T", "url": "http://x.com", "source": "S", "category": "markets", "published_at": "2026-05-11T08:00:00"}]
    with patch("aggregator.news.parse_rss", return_value=mock_items):
        with patch("aggregator.news.fetch_newsapi", return_value=[]):
            result = fetch_news("markets")
    assert len(result) >= 1
    assert result[0]["category"] == "markets"

def test_fetch_news_deduplicates_by_url():
    duplicate = {"title": "Same", "url": "http://a.com", "source": "S", "category": "trading", "published_at": None}
    with patch("aggregator.news.parse_rss", return_value=[duplicate, duplicate]):
        with patch("aggregator.news.fetch_newsapi", return_value=[duplicate]):
            result = fetch_news("trading")
    urls = [r["url"] for r in result]
    assert urls.count("http://a.com") == 1


def test_fetch_news_keeps_items_with_different_titles_but_the_same_url():
    """url is the uniqueness contract now, not title — a re-syndicated
    headline sharing a url with an earlier item must still collapse."""
    a = {"title": "Original headline", "url": "http://shared.com", "source": "S", "category": "markets", "published_at": None}
    b = {"title": "Rewritten headline", "url": "http://shared.com", "source": "S", "category": "markets", "published_at": None}
    with patch("aggregator.news.parse_rss", return_value=[a, b]):
        with patch("aggregator.news.fetch_newsapi", return_value=[]):
            result = fetch_news("markets")
    assert len(result) == 1


def test_dedupe_keeps_items_with_no_url_distinct():
    """Falsy urls can't be used to tell items apart, so they must not
    collapse into a single item."""
    a = {"title": "A", "url": "", "source": "S", "category": "trading", "published_at": None}
    b = {"title": "B", "url": "", "source": "S", "category": "trading", "published_at": None}
    assert _dedupe([a, b]) == [a, b]


# --- Relevance filtering and source denial ---------------------------------

from aggregator.news import RSS_FEEDS, _is_denied_source, _is_relevant


def test_trading_relevance_is_unchanged():
    assert _is_relevant("Sensex rallies 500 points as RBI holds rates", "trading")
    assert not _is_relevant("Actor takes oath as chief minister", "trading")


def test_tech_accepts_real_ai_news():
    assert _is_relevant("OpenAI ships a new reasoning model", "tech")
    assert _is_relevant("Nvidia GPU supply tightens for datacenter buildouts", "tech")


def test_tech_rejects_entertainment():
    """Observed in production: Comic Book Movie matched the 'AI' keyword query."""
    assert not _is_relevant("Marvel reveals the trailer for its next film", "tech")
    assert not _is_relevant("Box office: sequel tops the weekend", "tech")


def test_energy_accepts_real_energy_news():
    assert _is_relevant("OPEC signals output cut as Brent slips", "energy")
    assert _is_relevant("Gigawatt-scale battery storage project approved", "energy")


def test_energy_rejects_car_auctions():
    """Observed in production: a car auction site matched the energy query."""
    assert not _is_relevant("This classic car is up for auction this week", "energy")


def test_unknown_category_accepts_everything():
    """A category with no lists configured must not silently drop all news."""
    assert _is_relevant("Anything at all", "unknown-category")


def test_denied_sources_are_rejected_case_insensitively():
    for bad in ["Bringatrailer.com", "naturalnews.com", "CBM (Comic Book Movie)",
                "Wattsupwiththat.com", "Deadline"]:
        assert _is_denied_source(bad), bad


def test_legitimate_sources_are_not_denied():
    for good in ["Economic Times", "Reuters", "MIT Tech Review", "OilPrice.com",
                 "CleanTechnica", "Business Standard"]:
        assert not _is_denied_source(good), good


def test_empty_source_is_not_denied():
    assert not _is_denied_source("")


def test_dead_feeds_are_gone():
    """These four were verified dead or blocking on 2026-09-05."""
    urls = [u for feeds in RSS_FEEDS.values() for u, _ in feeds]
    for dead in ["feeds.reuters.com/reuters/businessNews",
                 "feeds.reuters.com/reuters/energyNews",
                 "moneycontrol.com/rss/business.xml",
                 "venturebeat.com/category/ai/feed/"]:
        assert not any(dead in u for u in urls), dead


def test_every_category_has_at_least_one_source():
    # "geopolitics" is deliberately RSS-less (a886bc8): it's meant to come
    # from a licensed provider rather than scraped feeds, and relies on
    # NewsAPI alone until that provider exists. The real invariant is "some
    # source exists", not "an RSS feed exists" — this still catches a
    # category that was added with neither.
    for category in RSS_FEEDS:
        has_rss = len(RSS_FEEDS[category]) >= 1
        has_newsapi_query = bool(NEWSAPI_QUERIES.get(category, "").strip())
        assert has_rss or has_newsapi_query, category
