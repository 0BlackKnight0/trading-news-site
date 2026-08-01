# backend/tests/test_news.py
from unittest.mock import patch, MagicMock
from aggregator.news import fetch_news, parse_rss

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
    mock_items = [{"title": "T", "url": "http://x.com", "source": "S", "category": "trading", "published_at": "2026-05-11T08:00:00"}]
    with patch("aggregator.news.parse_rss", return_value=mock_items):
        with patch("aggregator.news.fetch_newsapi", return_value=[]):
            result = fetch_news("trading")
    assert len(result) >= 1
    assert result[0]["category"] == "trading"

def test_fetch_news_deduplicates_by_title():
    duplicate = {"title": "Same", "url": "http://a.com", "source": "S", "category": "trading", "published_at": None}
    with patch("aggregator.news.parse_rss", return_value=[duplicate, duplicate]):
        with patch("aggregator.news.fetch_newsapi", return_value=[duplicate]):
            result = fetch_news("trading")
    titles = [r["title"] for r in result]
    assert titles.count("Same") == 1
