# backend/tests/test_routes.py
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from identity import MIN_KEY_LENGTH, current_user

client = TestClient(app)

WL_HEADERS = {"X-Device-Key": "w" * MIN_KEY_LENGTH}


def _as_watchlist_user(user_id="u1"):
    app.dependency_overrides[current_user] = lambda: {"id": user_id}


def teardown_function():
    app.dependency_overrides.clear()

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

def test_get_market_enriches_rows_with_a_watchlist_target():
    """A market row's display symbol ("NIFTY") isn't Yahoo-fetchable on its
    own — the client needs the real ticker to add it to the watchlist."""
    mock_data = [{"symbol": "NIFTY", "price": 24832.0, "change_pct": 1.2, "category": "india"}]
    with patch("routes.market.refresh_market_if_stale"), \
         patch("routes.market.get_market", return_value=mock_data):
        data = client.get("/market").json()
    assert data[0]["watchlist_symbol"] == "^NSEI"
    assert data[0]["watchlist_type"] == "stock"

def test_get_market_reports_null_target_for_an_unmappable_row():
    mock_data = [{"symbol": "MADEUP", "price": 1.0, "change_pct": 0.0, "category": "india"}]
    with patch("routes.market.refresh_market_if_stale"), \
         patch("routes.market.get_market", return_value=mock_data):
        data = client.get("/market").json()
    assert data[0]["watchlist_symbol"] is None
    assert data[0]["watchlist_type"] is None

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

def test_watchlist_requires_a_device_key():
    assert client.get("/watchlist").status_code == 401


def test_watchlist_get_is_scoped_to_the_caller():
    _as_watchlist_user("u42")
    with patch("routes.watchlist.get_watchlist_quotes", return_value=[]) as getter:
        resp = client.get("/watchlist", headers=WL_HEADERS)
    assert resp.status_code == 200
    getter.assert_called_once_with("u42")


def test_watchlist_post_records_the_owner():
    _as_watchlist_user("u42")
    with patch("routes.watchlist.add_to_watchlist") as adder, \
         patch("routes.watchlist.refresh_symbol"):
        resp = client.post("/watchlist", json={"symbol": "RELIANCE", "type": "stock"},
                           headers=WL_HEADERS)
    assert resp.json()["symbol"] == "RELIANCE"
    adder.assert_called_once_with("u42", "RELIANCE", "stock")


def test_watchlist_post_backfills_the_new_symbol_immediately():
    """Without this, a symbol added via POST /watchlist has no
    price_snapshots until the next GLOBAL signals refresh — which can be up
    to SIGNALS_TTL (15 min) away regardless of when this symbol was added,
    since staleness is tracked once for all symbols, not per-symbol. The row
    shows "no data yet" the whole time, reading as if adding did nothing."""
    _as_watchlist_user("u42")
    with patch("routes.watchlist.add_to_watchlist"), \
         patch("routes.watchlist.refresh_symbol") as backfill:
        client.post("/watchlist", json={"symbol": "reliance", "type": "stock"},
                    headers=WL_HEADERS)
    backfill.assert_called_once_with("RELIANCE")


def test_watchlist_post_succeeds_even_if_the_backfill_fails():
    """A slow or failing Yahoo call must not turn a successful add into a
    500 — the symbol is on the watchlist either way; the price just waits
    for the next scheduled refresh instead of showing up instantly."""
    _as_watchlist_user("u42")
    with patch("routes.watchlist.add_to_watchlist"), \
         patch("routes.watchlist.refresh_symbol", side_effect=RuntimeError("yahoo down")):
        resp = client.post("/watchlist", json={"symbol": "AAPL", "type": "stock"},
                           headers=WL_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "added"


def test_watchlist_delete_is_scoped_to_the_caller():
    _as_watchlist_user("u42")
    with patch("routes.watchlist.remove_from_watchlist") as remover:
        resp = client.delete("/watchlist/RELIANCE", headers=WL_HEADERS)
    assert resp.json()["symbol"] == "RELIANCE"
    remover.assert_called_once_with("u42", "RELIANCE")


def test_admin_refresh_rejects_a_missing_secret(monkeypatch):
    """Currently open to the world — anyone can trigger a full refresh."""
    monkeypatch.setenv("CRON_SECRET", "s3cret-value-1234")
    assert client.post("/admin/refresh").status_code == 401


def test_admin_refresh_accepts_the_cron_secret(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret-value-1234")
    with patch("routes.admin.run_market_refresh"), patch("routes.admin.run_news_refresh"), \
         patch("routes.admin.get_market", return_value=[]), \
         patch("routes.admin.get_news", return_value=[]):
        resp = client.post("/admin/refresh",
                           headers={"Authorization": "Bearer s3cret-value-1234"})
    assert resp.status_code == 200


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
         patch("routes.cron.run_signals_refresh", return_value=5) as signals, \
         patch("routes.cron.send_digest", return_value=2) as digest:
        resp = client.get("/cron/daily", headers={"Authorization": "Bearer s3cret-value-1234"})
    assert resp.status_code == 200
    assert resp.json() == {
        "market": 12, "news": 30, "signals": 5, "digest_sent": 2, "errors": {},
    }
    market.assert_called_once()
    news.assert_called_once()
    signals.assert_called_once()
    digest.assert_called_once()

def test_cron_refreshes_signals_before_news(monkeypatch):
    """Signals refresh fetches each symbol's company name; news refresh tags
    articles against those names. Running news first tags nothing on a
    database that has never had a signals refresh — a real bug caught live
    on the first production run after this feature shipped."""
    monkeypatch.setenv("CRON_SECRET", "s3cret-value-1234")
    order = []
    with patch("routes.cron.run_market_refresh", return_value=0), \
         patch("routes.cron.run_news_refresh", side_effect=lambda: order.append("news") or 0), \
         patch("routes.cron.run_signals_refresh", side_effect=lambda: order.append("signals") or 0), \
         patch("routes.cron.send_digest", return_value=0):
        client.get("/cron/daily", headers={"Authorization": "Bearer s3cret-value-1234"})
    assert order == ["signals", "news"]

def test_cron_reports_partial_failure(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret-value-1234")
    with patch("routes.cron.run_market_refresh", side_effect=RuntimeError("yahoo down")), \
         patch("routes.cron.run_news_refresh", return_value=30), \
         patch("routes.cron.run_signals_refresh", return_value=5), \
         patch("routes.cron.send_digest", return_value=1):
        resp = client.get("/cron/daily", headers={"Authorization": "Bearer s3cret-value-1234"})
    body = resp.json()
    assert resp.status_code == 200
    assert body["market"] is None
    assert "yahoo down" in body["errors"]["market"]
    assert body["news"] == 30
    assert body["signals"] == 5


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

def test_watchlist_rows_carry_price_and_as_of():
    _as_watchlist_user("u42")
    rows = [{"id": 1, "symbol": "X", "type": "stock", "price": 105.0,
             "change_pct": 5.0, "as_of": "2026-03-04T00:00:00+00:00"}]
    with patch("routes.watchlist.get_watchlist_quotes", return_value=rows):
        body = client.get("/watchlist", headers=WL_HEADERS).json()
    assert body[0]["price"] == 105.0
    assert body[0]["as_of"] == "2026-03-04T00:00:00+00:00"


def test_watchlist_row_without_history_reports_null_price_not_zero():
    """A missing price must read as unknown, never as a real value of zero."""
    _as_watchlist_user("u42")
    rows = [{"id": 1, "symbol": "NEW", "type": "stock", "price": None,
             "change_pct": None, "as_of": None}]
    with patch("routes.watchlist.get_watchlist_quotes", return_value=rows):
        body = client.get("/watchlist", headers=WL_HEADERS).json()
    assert body[0]["price"] is None
