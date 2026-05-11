# backend/tests/test_routes.py
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app

client = TestClient(app)

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

def test_get_market():
    mock_data = [{"symbol": "NIFTY", "price": 24832.0, "change_pct": 1.2, "category": "india"}]
    with patch("routes.market.get_market", return_value=mock_data):
        resp = client.get("/market")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["symbol"] == "NIFTY"

def test_get_news_by_category():
    mock_data = [{"title": "Test", "url": "http://x.com", "source": "ET", "category": "trading", "published_at": None}]
    with patch("routes.news.get_news", return_value=mock_data):
        resp = client.get("/news?category=trading")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["category"] == "trading"

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
