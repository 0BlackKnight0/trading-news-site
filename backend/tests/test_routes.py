# backend/tests/test_routes.py
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

def test_get_market():
    mock_data = [{"symbol": "NIFTY", "price": 24832.0, "change_pct": 1.2, "category": "india"}]
    with patch("routes.market.refresh_market_if_stale"), \
         patch("routes.market.get_market", return_value=mock_data):
        resp = client.get("/market")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["symbol"] == "NIFTY"

def test_get_market_revalidates_before_reading():
    with patch("routes.market.refresh_market_if_stale") as refresh, \
         patch("routes.market.get_market", return_value=[]):
        client.get("/market")
    refresh.assert_called_once()

def test_get_news_by_category():
    mock_data = [{"title": "Test", "url": "http://x.com", "source": "ET", "category": "trading", "published_at": None}]
    with patch("routes.news.refresh_news_if_stale"), \
         patch("routes.news.get_news", return_value=mock_data):
        resp = client.get("/news?category=trading")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["category"] == "trading"

def test_get_news_revalidates_before_reading():
    with patch("routes.news.refresh_news_if_stale") as refresh, \
         patch("routes.news.get_news", return_value=[]):
        client.get("/news?category=tech")
    refresh.assert_called_once()

def test_watchlist_get():
    with patch("routes.watchlist.get_watchlist", return_value=[]):
        resp = client.get("/watchlist")
    assert resp.status_code == 200

def test_watchlist_post():
    with patch("routes.watchlist.add_to_watchlist"):
        resp = client.post("/watchlist", json={"symbol": "RELIANCE", "type": "stock"})
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "RELIANCE"

def test_watchlist_delete():
    with patch("routes.watchlist.remove_from_watchlist"):
        resp = client.delete("/watchlist/RELIANCE")
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "RELIANCE"


# --- Cron -----------------------------------------------------------------

def test_cron_rejects_missing_secret(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret-value-1234")
    resp = client.get("/cron/daily")
    assert resp.status_code == 401

def test_cron_rejects_wrong_secret(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret-value-1234")
    resp = client.get("/cron/daily", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401

def test_cron_closed_when_secret_unconfigured(monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    resp = client.get("/cron/daily", headers={"Authorization": "Bearer anything"})
    assert resp.status_code == 401

def test_cron_runs_refresh_and_digest(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret-value-1234")
    with patch("routes.cron.run_market_refresh", return_value=12) as market, \
         patch("routes.cron.run_news_refresh", return_value=30) as news, \
         patch("routes.cron.send_digest", return_value=2) as digest:
        resp = client.get("/cron/daily", headers={"Authorization": "Bearer s3cret-value-1234"})
    assert resp.status_code == 200
    assert resp.json() == {
        "market": 12, "news": 30, "digest_sent": 2, "errors": {},
    }
    market.assert_called_once()
    news.assert_called_once()
    digest.assert_called_once()

def test_cron_reports_partial_failure(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret-value-1234")
    with patch("routes.cron.run_market_refresh", side_effect=RuntimeError("yahoo down")), \
         patch("routes.cron.run_news_refresh", return_value=30), \
         patch("routes.cron.send_digest", return_value=1):
        resp = client.get("/cron/daily", headers={"Authorization": "Bearer s3cret-value-1234"})
    body = resp.json()
    assert resp.status_code == 200
    assert body["market"] is None
    assert "yahoo down" in body["errors"]["market"]
    assert body["news"] == 30


# --- Telegram webhook ------------------------------------------------------

def test_webhook_rejects_bad_secret(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "hook-secret")
    resp = client.post(
        "/telegram/webhook",
        json={"message": {}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "nope"},
    )
    assert resp.status_code == 401

def test_webhook_accepts_valid_secret(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "hook-secret")
    with patch("routes.telegram.handle_update") as handler:
        resp = client.post(
            "/telegram/webhook",
            json={"message": {"chat": {"id": 1}, "text": "/start"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "hook-secret"},
        )
    assert resp.status_code == 200
    handler.assert_called_once()

def test_webhook_swallows_handler_errors(monkeypatch):
    """Telegram retries on non-200, so a bad update must not surface as 500."""
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    with patch("routes.telegram.handle_update", side_effect=RuntimeError("boom")):
        resp = client.post("/telegram/webhook", json={"message": {}})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
