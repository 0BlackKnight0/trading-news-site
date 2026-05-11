# backend/tests/test_market.py
from unittest.mock import patch, MagicMock
from aggregator.market import fetch_india, fetch_crypto, fetch_forex


def test_fetch_india_returns_nifty_and_sensex():
    mock_index_data = {"last": 24832.0, "percentChange": 1.17}
    with patch("aggregator.market.nse_index", return_value=mock_index_data):
        with patch("aggregator.market.NSE_AVAILABLE", True):
            result = fetch_india()
    symbols = [r["symbol"] for r in result]
    assert "NIFTY" in symbols
    assert "SENSEX" in symbols
    for item in result:
        assert "price" in item
        assert "change_pct" in item
        assert item["category"] == "india"


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
    mock_ticker = MagicMock()
    mock_ticker.info = {"regularMarketPrice": 83.42, "regularMarketChangePercent": -0.2}
    with patch("aggregator.market.yf.Ticker", return_value=mock_ticker):
        result = fetch_forex()
    symbols = [r["symbol"] for r in result]
    assert "USD/INR" in symbols
