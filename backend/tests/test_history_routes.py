# backend/tests/test_history_routes.py
from unittest.mock import patch

from fastapi.testclient import TestClient

from identity import MIN_KEY_LENGTH, current_user
from main import app

client = TestClient(app)
HEADERS = {"X-Device-Key": "k" * MIN_KEY_LENGTH}


def _as_user(user_id="u1"):
    app.dependency_overrides[current_user] = lambda: {"id": user_id}


def teardown_function():
    app.dependency_overrides.clear()


def test_history_requires_a_device_key():
    assert client.get("/history?symbol=RELIANCE.NS").status_code == 401


def test_history_404s_for_a_symbol_not_on_the_callers_watchlist():
    _as_user()
    with patch("routes.history.get_watchlist", return_value=[{"symbol": "TCS.NS"}]):
        resp = client.get("/history?symbol=RELIANCE.NS", headers=HEADERS)
    assert resp.status_code == 404


def test_history_defaults_the_range_to_last_seen_through_now():
    _as_user()
    with patch("routes.history.get_watchlist", return_value=[{"symbol": "RELIANCE.NS"}]), \
         patch("routes.history.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.history._utc_now_iso", return_value="2026-03-05T00:00:00+00:00"), \
         patch("routes.history.get_snapshot_range", return_value=[]) as getter:
        client.get("/history?symbol=RELIANCE.NS", headers=HEADERS)
    getter.assert_called_once_with(
        "RELIANCE.NS", "2026-03-01T00:00:00+00:00", "2026-03-05T00:00:00+00:00")


def test_history_lets_explicit_from_and_to_override_the_defaults():
    _as_user()
    with patch("routes.history.get_watchlist", return_value=[{"symbol": "RELIANCE.NS"}]), \
         patch("routes.history.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.history.get_snapshot_range", return_value=[]) as getter:
        client.get(
            "/history?symbol=RELIANCE.NS&from=2026-02-01T00:00:00%2B00:00"
            "&to=2026-02-15T00:00:00%2B00:00",
            headers=HEADERS,
        )
    getter.assert_called_once_with(
        "RELIANCE.NS", "2026-02-01T00:00:00+00:00", "2026-02-15T00:00:00+00:00")


def test_history_returns_last_seen_at_and_bars():
    _as_user()
    bars = [{"ts": "2026-03-02T00:00:00+00:00", "close": 1432.1}]
    with patch("routes.history.get_watchlist", return_value=[{"symbol": "RELIANCE.NS"}]), \
         patch("routes.history.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.history.get_snapshot_range", return_value=bars):
        resp = client.get("/history?symbol=RELIANCE.NS", headers=HEADERS)
    body = resp.json()
    assert resp.status_code == 200
    assert body["symbol"] == "RELIANCE.NS"
    assert body["last_seen_at"] == "2026-03-01T00:00:00+00:00"
    assert body["bars"] == bars


def test_history_uppercases_the_symbol_before_checking_ownership():
    _as_user()
    with patch("routes.history.get_watchlist", return_value=[{"symbol": "RELIANCE.NS"}]), \
         patch("routes.history.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.history.get_snapshot_range", return_value=[]) as getter:
        resp = client.get("/history?symbol=reliance.ns", headers=HEADERS)
    assert resp.status_code == 200
    assert getter.call_args[0][0] == "RELIANCE.NS"
