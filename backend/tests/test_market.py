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
