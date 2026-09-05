# backend/aggregator/yahoo.py
"""Thin Yahoo Finance client.

Calls the public v8 chart API directly instead of going through yfinance.
Keeps the serverless bundle small (no pandas/numpy) and avoids the scraping
that made yfinance/nsepython unreliable from datacenter IPs.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

import requests

from datetime import datetime, timezone

from signals.types import Bar

logger = logging.getLogger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
TIMEOUT = 10
MAX_WORKERS = 8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finance.yahoo.com/",
    "Origin": "https://finance.yahoo.com",
}


def fetch_chart(symbol: str, interval: str = "1d", range_: str = "5d") -> dict:
    """Return the raw chart result for a symbol, or {} on any failure."""
    try:
        resp = requests.get(
            CHART_URL.format(symbol=symbol),
            params={"interval": interval, "range": range_, "events": "div,splits"},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        results = resp.json().get("chart", {}).get("result") or []
        return results[0] if results else {}
    except Exception as e:
        logger.error(f"chart API failed for {symbol}: {e}")
        return {}


def quote_from_chart(chart: dict) -> dict | None:
    """Derive price / prev_close / change from a chart result.

    Previous close comes from the second-to-last daily close rather than
    meta.chartPreviousClose, which lags for some symbols.
    """
    meta = chart.get("meta") or {}
    if not meta:
        return None

    price = float(meta.get("regularMarketPrice") or 0)
    if not price:
        return None

    quotes = (chart.get("indicators") or {}).get("quote") or [{}]
    ohlcv = quotes[0] if quotes else {}
    closes = [v for v in (ohlcv.get("close") or []) if v is not None]
    opens = [v for v in (ohlcv.get("open") or []) if v is not None]

    prev_close = (
        float(closes[-2]) if len(closes) >= 2
        else float(meta.get("chartPreviousClose") or 0)
    )
    change_abs = price - prev_close if prev_close else 0.0
    change_pct = (change_abs / prev_close * 100) if prev_close else 0.0

    return {
        "name": meta.get("longName") or meta.get("shortName") or meta.get("symbol"),
        "price": price,
        "prev_close": prev_close or None,
        "open": float(opens[-1]) if opens else None,
        "change_abs": change_abs,
        "change_pct": change_pct,
        "currency": meta.get("currency") or "USD",
        "volume": meta.get("regularMarketVolume") or None,
        "market_cap": meta.get("marketCap") or None,
        "week_52_high": meta.get("fiftyTwoWeekHigh") or None,
        "week_52_low": meta.get("fiftyTwoWeekLow") or None,
    }


def fetch_quotes(symbols: list[str]) -> dict[str, dict]:
    """Fetch several symbols concurrently. Missing/failed symbols are omitted.

    Serverless invocations are billed on wall-clock, so these go out in
    parallel rather than one at a time.
    """
    if not symbols:
        return {}

    def one(symbol: str) -> tuple[str, dict | None]:
        return symbol, quote_from_chart(fetch_chart(symbol))

    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(symbols))) as pool:
        for symbol, quote in pool.map(one, symbols):
            if quote:
                out[symbol] = quote
    return out


def bars_from_chart(chart: dict) -> list[Bar]:
    """Extract ascending daily bars from a chart result.

    Yahoo pads the series with nulls on non-trading days; those rows are
    dropped rather than carried forward, so averages are not diluted.
    """
    timestamps = chart.get("timestamp") or []
    quotes = (chart.get("indicators") or {}).get("quote") or [{}]
    ohlcv = quotes[0] if quotes else {}

    closes = ohlcv.get("close") or []
    opens = ohlcv.get("open") or []
    highs = ohlcv.get("high") or []
    lows = ohlcv.get("low") or []
    volumes = ohlcv.get("volume") or []

    def at(series, i):
        return series[i] if i < len(series) else None

    bars = []
    for i, epoch in enumerate(timestamps):
        close = at(closes, i)
        if close is None:
            continue
        ts = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
        volume = at(volumes, i)
        bars.append(Bar(
            ts=ts,
            open=at(opens, i),
            high=at(highs, i),
            low=at(lows, i),
            close=float(close),
            volume=int(volume) if volume is not None else None,
        ))
    return bars


def fetch_bars(symbol: str, range_: str = "3mo") -> list[Bar]:
    """Daily bars for a symbol. Returns [] on any failure."""
    try:
        return bars_from_chart(fetch_chart(symbol, interval="1d", range_=range_))
    except Exception as e:
        logger.error(f"bar parse failed for {symbol}: {e}")
        return []
