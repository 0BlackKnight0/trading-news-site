# backend/tests/test_search.py
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app
from routes.search import _map_quote

client = TestClient(app)


def _quote(symbol, qtype, name=None, exchange="NSE"):
    return {"symbol": symbol, "quoteType": qtype, "shortname": name,
            "exchDisp": exchange}


# --- _map_quote (pure) ------------------------------------------------------

def test_map_quote_maps_equity_to_stock():
    assert _map_quote(_quote("AAPL", "EQUITY", "Apple Inc."))["type"] == "stock"


def test_map_quote_maps_etf_and_mutualfund_to_stock():
    assert _map_quote(_quote("SPY", "ETF"))["type"] == "stock"
    assert _map_quote(_quote("VFIAX", "MUTUALFUND"))["type"] == "stock"


def test_map_quote_maps_cryptocurrency_to_crypto():
    assert _map_quote(_quote("BTC-USD", "CRYPTOCURRENCY"))["type"] == "crypto"


def test_map_quote_maps_currency_to_forex():
    assert _map_quote(_quote("USDINR=X", "CURRENCY"))["type"] == "forex"


def test_map_quote_rejects_unsupported_types():
    assert _map_quote(_quote("SOMEINDEX", "INDEX")) is None


def test_map_quote_falls_back_to_longname_then_symbol():
    item = {"symbol": "X", "quoteType": "EQUITY", "shortname": None,
            "longname": "X Corp", "exchDisp": "NYSE"}
    assert _map_quote(item)["name"] == "X Corp"
    item["longname"] = None
    assert _map_quote(item)["name"] == "X"


# --- /search route -----------------------------------------------------------

def test_search_returns_mapped_results():
    resp = MagicMock()
    resp.json.return_value = {"quotes": [_quote("AAPL", "EQUITY", "Apple Inc.")]}
    with patch("routes.search.requests.get", return_value=resp):
        body = client.get("/search?q=apple").json()
    assert body == [{"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NSE", "type": "stock"}]


def test_search_caps_results_at_seven():
    resp = MagicMock()
    resp.json.return_value = {"quotes": [_quote(f"S{i}", "EQUITY") for i in range(10)]}
    with patch("routes.search.requests.get", return_value=resp):
        body = client.get("/search?q=s").json()
    assert len(body) == 7


def test_search_survives_a_failed_request():
    with patch("routes.search.requests.get", side_effect=TimeoutError("no")):
        assert client.get("/search?q=x").json() == []


def test_search_without_a_type_filter_uses_the_default_quote_count():
    resp = MagicMock()
    resp.json.return_value = {"quotes": []}
    with patch("routes.search.requests.get", return_value=resp) as get:
        client.get("/search?q=apple")
    assert "quotesCount=8" in get.call_args[0][0]


def test_search_with_a_type_filter_only_returns_that_type():
    resp = MagicMock()
    resp.json.return_value = {"quotes": [
        _quote("AAPL", "EQUITY"), _quote("BTC-USD", "CRYPTOCURRENCY"),
        _quote("USDINR=X", "CURRENCY"),
    ]}
    with patch("routes.search.requests.get", return_value=resp):
        body = client.get("/search?q=a&type=crypto").json()
    assert [r["symbol"] for r in body] == ["BTC-USD"]


def test_search_with_a_type_filter_widens_the_upstream_query():
    """Yahoo's top matches for a plain query skew toward one instrument type
    (a ticker mostly returns stocks) — fetching more raw candidates when a
    filter is active is what lets "crypto" surface crypto results instead of
    an empty list filtered out of an all-stock top 8."""
    resp = MagicMock()
    resp.json.return_value = {"quotes": []}
    with patch("routes.search.requests.get", return_value=resp) as get:
        client.get("/search?q=apple&type=crypto")
    assert "quotesCount=8" not in get.call_args[0][0]


def test_search_type_filter_still_caps_at_seven():
    resp = MagicMock()
    resp.json.return_value = {"quotes": [_quote(f"C{i}", "CRYPTOCURRENCY") for i in range(15)]}
    with patch("routes.search.requests.get", return_value=resp):
        body = client.get("/search?q=c&type=crypto").json()
    assert len(body) == 7


def test_search_with_an_unknown_type_returns_nothing_rather_than_erroring():
    # Consistent with /news?category=: `enum=` on a plain str Query is
    # documentation only in this FastAPI version, not runtime validation —
    # an unrecognised value simply matches no result rather than 422ing.
    resp = MagicMock()
    resp.json.return_value = {"quotes": [_quote("AAPL", "EQUITY")]}
    with patch("routes.search.requests.get", return_value=resp):
        body = client.get("/search?q=apple&type=nonsense").json()
    assert body == []
