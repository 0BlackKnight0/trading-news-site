# backend/tests/test_yahoo.py
from aggregator.yahoo import quote_from_chart


def _chart(price, closes, opens=None, **meta):
    return {
        "meta": {"regularMarketPrice": price, "currency": "INR", **meta},
        "indicators": {"quote": [{"close": closes, "open": opens or []}]},
    }


def test_prev_close_uses_second_to_last_close():
    quote = quote_from_chart(_chart(110.0, [90.0, 100.0, 110.0]))
    assert quote["prev_close"] == 100.0
    assert quote["change_abs"] == 10.0
    assert round(quote["change_pct"], 2) == 10.0


def test_ignores_null_closes():
    """Yahoo pads the series with nulls on non-trading days."""
    quote = quote_from_chart(_chart(110.0, [90.0, None, 100.0, None]))
    assert quote["prev_close"] == 90.0


def test_falls_back_to_chart_previous_close():
    chart = _chart(110.0, [110.0], chartPreviousClose=105.0)
    quote = quote_from_chart(chart)
    assert quote["prev_close"] == 105.0
    assert round(quote["change_pct"], 2) == 4.76


def test_zero_prev_close_does_not_divide_by_zero():
    quote = quote_from_chart(_chart(110.0, [], chartPreviousClose=0))
    assert quote["prev_close"] is None
    assert quote["change_pct"] == 0.0


def test_open_comes_from_latest_session():
    quote = quote_from_chart(_chart(110.0, [100.0, 110.0], opens=[98.0, 104.0]))
    assert quote["open"] == 104.0


def test_returns_none_without_meta():
    assert quote_from_chart({}) is None


def test_returns_none_when_price_missing():
    assert quote_from_chart(_chart(0, [100.0])) is None
