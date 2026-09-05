# backend/tests/test_market.py
from unittest.mock import MagicMock, patch

from aggregator.market import fetch_crypto, fetch_forex, fetch_india


def _quotes(symbols: list[str], price: float, change_pct: float) -> dict:
    return {
        s: {"price": price, "change_pct": change_pct, "prev_close": price, "open": price,
            "change_abs": 0.0, "currency": "USD", "name": s, "volume": None,
            "market_cap": None, "week_52_high": None, "week_52_low": None}
        for s in symbols
    }


def test_fetch_india_returns_nifty_and_sensex():
    with patch(
        "aggregator.market.fetch_quotes",
        return_value=_quotes(["^NSEI", "^BSESN", "^NSEBANK"], 24832.0, 1.17),
    ):
        result = fetch_india()
    symbols = [r["symbol"] for r in result]
    assert "NIFTY" in symbols
    assert "SENSEX" in symbols
    for item in result:
        assert "price" in item
        assert "change_pct" in item
        assert item["category"] == "india"


def test_fetch_india_skips_symbols_yahoo_omits():
    with patch("aggregator.market.fetch_quotes", return_value=_quotes(["^NSEI"], 100.0, 0.5)):
        result = fetch_india()
    assert [r["symbol"] for r in result] == ["NIFTY"]


def test_fetch_crypto_returns_btc_and_eth():
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"symbol": "btc", "current_price": 67420, "price_change_percentage_24h": 2.1},
        {"symbol": "eth", "current_price": 3210, "price_change_percentage_24h": -0.5},
    ]
    with patch("aggregator.market.requests.get", return_value=mock_response):
        result = fetch_crypto()
    symbols = [r["symbol"] for r in result]
    assert "BTC" in symbols
    assert "ETH" in symbols


def test_fetch_forex_returns_usd_inr():
    with patch(
        "aggregator.market.fetch_quotes",
        return_value=_quotes(["USDINR=X", "EURUSD=X", "GBPUSD=X", "EURINR=X"], 83.42, -0.2),
    ):
        result = fetch_forex()
    symbols = [r["symbol"] for r in result]
    assert "USD/INR" in symbols


# --- watchlist_target ---------------------------------------------------

from aggregator.market import watchlist_target


def test_watchlist_target_maps_india_display_symbols_to_stock():
    assert watchlist_target("NIFTY", "india") == ("^NSEI", "stock")
    assert watchlist_target("SENSEX", "india") == ("^BSESN", "stock")


def test_watchlist_target_maps_global_display_symbols_to_stock():
    assert watchlist_target("S&P 500", "global") == ("^GSPC", "stock")
    assert watchlist_target("GOLD", "global") == ("GC=F", "stock")


def test_watchlist_target_maps_forex_display_symbols_to_forex():
    assert watchlist_target("USD/INR", "forex") == ("USDINR=X", "forex")


def test_watchlist_target_maps_crypto_display_symbols_to_crypto():
    assert watchlist_target("BTC", "crypto") == ("BTC-USD", "crypto")
    assert watchlist_target("DOGE", "crypto") == ("DOGE-USD", "crypto")


def test_watchlist_target_is_none_for_an_unknown_symbol_in_a_known_category():
    """A symbol market_cache doesn't actually populate for that category —
    defensive, should never happen with the current fetch lists."""
    assert watchlist_target("MADEUP", "india") is None


def test_watchlist_target_is_none_for_an_unknown_category():
    assert watchlist_target("NIFTY", "made-up-category") is None
