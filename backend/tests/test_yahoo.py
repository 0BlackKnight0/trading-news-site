# backend/tests/test_yahoo.py
import aggregator.yahoo as yahoo
from aggregator.yahoo import fetch_bars, quote_from_chart


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


# --- Bar extraction -------------------------------------------------------

from aggregator.yahoo import bars_from_chart


def _chart_with_series(timestamps, opens, highs, lows, closes, volumes):
    return {
        "meta": {"regularMarketPrice": closes[-1], "currency": "INR"},
        "timestamp": timestamps,
        "indicators": {"quote": [{
            "open": opens, "high": highs, "low": lows,
            "close": closes, "volume": volumes,
        }]},
    }


def test_bars_from_chart_builds_ascending_bars():
    chart = _chart_with_series(
        [1767225600, 1767312000], [100.0, 102.0], [103.0, 105.0],
        [99.0, 101.0], [102.0, 104.0], [1000, 2000],
    )
    bars = bars_from_chart(chart)
    assert len(bars) == 2
    assert bars[0].close == 102.0
    assert bars[1].volume == 2000
    assert bars[0].ts < bars[1].ts


def test_bars_from_chart_drops_rows_with_no_close():
    """Yahoo pads the series with nulls on non-trading days."""
    chart = _chart_with_series(
        [1767225600, 1767312000], [100.0, None], [103.0, None],
        [99.0, None], [102.0, None], [1000, None],
    )
    bars = bars_from_chart(chart)
    assert len(bars) == 1


def test_bars_from_chart_returns_empty_for_an_empty_chart():
    assert bars_from_chart({}) == []


def test_bars_timestamps_are_iso_utc():
    chart = _chart_with_series([1767225600], [100.0], [103.0], [99.0], [102.0], [1000])
    assert bars_from_chart(chart)[0].ts.endswith("+00:00")


# --- fetch_bars degrades to [] instead of raising -------------------------


def test_fetch_bars_returns_empty_when_quote_is_null(monkeypatch):
    """Yahoo can return indicators.quote == [None] for a symbol with no data
    in the requested range; [None] is truthy so it must not raise."""
    chart = {
        "meta": {"regularMarketPrice": 1.0},
        "timestamp": [1767225600],
        "indicators": {"quote": [None]},
    }
    monkeypatch.setattr(yahoo, "fetch_chart", lambda *a, **k: chart)
    assert fetch_bars("BADSYM") == []


def test_fetch_bars_returns_empty_when_timestamp_has_null(monkeypatch):
    """A None inside the timestamp array must not raise from datetime.fromtimestamp."""
    chart = _chart_with_series(
        [1767225600, None], [100.0, 102.0], [103.0, 105.0],
        [99.0, 101.0], [102.0, 104.0], [1000, 2000],
    )
    monkeypatch.setattr(yahoo, "fetch_chart", lambda *a, **k: chart)
    assert fetch_bars("BADSYM") == []


# --- fetch_symbol_name ------------------------------------------------------

from aggregator.yahoo import fetch_symbol_name


def test_fetch_symbol_name_returns_long_name(monkeypatch):
    chart = {"meta": {"longName": "Infosys Limited", "shortName": "INFY"}}
    monkeypatch.setattr(yahoo, "fetch_chart", lambda *a, **k: chart)
    assert fetch_symbol_name("INFY.NS") == "Infosys Limited"


def test_fetch_symbol_name_falls_back_to_short_name(monkeypatch):
    chart = {"meta": {"shortName": "INFY"}}
    monkeypatch.setattr(yahoo, "fetch_chart", lambda *a, **k: chart)
    assert fetch_symbol_name("INFY.NS") == "INFY"


def test_fetch_symbol_name_returns_none_for_empty_chart(monkeypatch):
    monkeypatch.setattr(yahoo, "fetch_chart", lambda *a, **k: {})
    assert fetch_symbol_name("BADSYM") is None


def test_fetch_symbol_name_returns_none_on_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(yahoo, "fetch_chart", boom)
    assert fetch_symbol_name("BADSYM") is None
