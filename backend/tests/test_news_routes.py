# backend/tests/test_news_routes.py
from unittest.mock import patch

from fastapi.testclient import TestClient

from identity import MIN_KEY_LENGTH, current_user
from main import app

client = TestClient(app)
HEADERS = {"X-Device-Key": "n" * MIN_KEY_LENGTH}

ARTICLE = {"id": 1, "title": "Reliance Q2 beats", "url": "http://ex.com/1",
           "source": "Economic Times", "category": None, "symbol": "RELIANCE.NS",
           "published_at": "2026-09-04T10:00:00+00:00", "summary": "x", "score": 5}


def _as_user(user_id="u1"):
    app.dependency_overrides[current_user] = lambda: {"id": user_id}


def teardown_function():
    app.dependency_overrides.clear()


def test_symbol_news_requires_a_device_key():
    assert client.get("/news/symbols").status_code == 401


def test_symbol_news_returns_articles_and_unread():
    _as_user()
    with patch("routes.news.refresh_signals_if_stale"), \
         patch("routes.news.refresh_news_if_stale"), \
         patch("routes.news.get_watchlist", return_value=[{"symbol": "RELIANCE.NS"}]), \
         patch("routes.news.get_news_last_seen", return_value="2026-09-01T00:00:00+00:00"), \
         patch("routes.news.get_symbol_news", return_value=[ARTICLE]), \
         patch("routes.news.count_news_since", return_value=4):
        body = client.get("/news/symbols", headers=HEADERS).json()
    assert body["unread_count"] == 4
    assert body["items"][0]["symbol"] == "RELIANCE.NS"
    assert body["news_last_seen_at"] == "2026-09-01T00:00:00+00:00"


def test_symbol_news_is_scoped_to_the_callers_watchlist():
    _as_user("u42")
    with patch("routes.news.refresh_signals_if_stale"), \
         patch("routes.news.refresh_news_if_stale"), \
         patch("routes.news.get_watchlist", return_value=[{"symbol": "AAPL"}]) as wl, \
         patch("routes.news.get_news_last_seen", return_value="2026-09-01T00:00:00+00:00"), \
         patch("routes.news.get_symbol_news", return_value=[]) as getter, \
         patch("routes.news.count_news_since", return_value=0):
        client.get("/news/symbols", headers=HEADERS)
    wl.assert_called_once_with("u42")
    assert getter.call_args[0][0] == ["AAPL"]


def test_symbol_news_with_an_empty_watchlist_returns_nothing():
    _as_user()
    with patch("routes.news.refresh_signals_if_stale"), \
         patch("routes.news.refresh_news_if_stale"), \
         patch("routes.news.get_watchlist", return_value=[]), \
         patch("routes.news.get_news_last_seen", return_value="2026-09-01T00:00:00+00:00"), \
         patch("routes.news.get_symbol_news", return_value=[]), \
         patch("routes.news.count_news_since", return_value=0):
        body = client.get("/news/symbols", headers=HEADERS).json()
    assert body["items"] == []
    assert body["unread_count"] == 0


def test_news_seen_advances_the_news_baseline_only():
    _as_user()
    with patch("routes.news.set_news_last_seen", return_value="2026-09-05T00:00:00+00:00") as setter:
        body = client.post("/news/seen", headers=HEADERS).json()
    assert body["news_last_seen_at"] == "2026-09-05T00:00:00+00:00"
    setter.assert_called_once_with("u1")


def test_news_seen_requires_a_device_key():
    assert client.post("/news/seen").status_code == 401


def test_category_news_stays_anonymous():
    """Market news is not user-specific — no device key required."""
    with patch("routes.news.refresh_signals_if_stale"), \
         patch("routes.news.refresh_news_if_stale"), \
         patch("routes.news.get_news", return_value=[]):
        assert client.get("/news?category=trading").status_code == 200


def test_symbol_news_ensures_signals_are_fresh_before_reading():
    """Signals are what fetch each symbol's company name (see
    pipeline._ensure_symbol_names) — news tagging needs that name to exist.
    Without this, a name is missing purely because nobody happened to hit
    /feed first."""
    _as_user()
    with patch("routes.news.refresh_signals_if_stale") as signals, \
         patch("routes.news.refresh_news_if_stale"), \
         patch("routes.news.get_watchlist", return_value=[]), \
         patch("routes.news.get_news_last_seen", return_value="2026-09-01T00:00:00+00:00"), \
         patch("routes.news.get_symbol_news", return_value=[]), \
         patch("routes.news.count_news_since", return_value=0):
        client.get("/news/symbols", headers=HEADERS)
    signals.assert_called_once()


def test_category_news_also_ensures_signals_are_fresh():
    with patch("routes.news.refresh_signals_if_stale") as signals, \
         patch("routes.news.refresh_news_if_stale"), \
         patch("routes.news.get_news", return_value=[]):
        client.get("/news?category=markets")
    signals.assert_called_once()
