# backend/routes/ticker.py
import logging
from datetime import datetime, timezone
import requests
from fastapi import APIRouter, Query

router = APIRouter()
logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finance.yahoo.com/",
    "Origin": "https://finance.yahoo.com",
}
_TIMEOUT = 10


def _chart(symbol: str) -> dict:
    """Fetch price + meta from Yahoo Finance v8 chart API. One call gets everything."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": "1d", "range": "5d", "events": "div,splits"}
    try:
        r = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
        results = r.json().get("chart", {}).get("result") or []
        return results[0] if results else {}
    except Exception as e:
        logger.error(f"chart API failed for {symbol}: {e}")
        return {}


def _news(symbol: str) -> list[dict]:
    """Fetch recent news from Yahoo Finance search API."""
    try:
        r = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": symbol, "newsCount": 8, "quotesCount": 0},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        items = r.json().get("news") or []
        out = []
        for item in items:
            title = item.get("title", "")
            if not title:
                continue
            ts = item.get("providerPublishTime")
            pub = (
                datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                if ts else ""
            )
            out.append({
                "title": title,
                "url": item.get("link", ""),
                "source": item.get("publisher", ""),
                "published_at": pub,
                "summary": item.get("summary", "") or "",
            })
        return out
    except Exception as e:
        logger.error(f"news API failed for {symbol}: {e}")
        return []


@router.get("/ticker/{symbol}")
def ticker_detail(symbol: str, type: str = Query(default="stock")):
    symbol = symbol.upper()

    result: dict = {
        "symbol": symbol,
        "name": symbol,
        "price": 0.0,
        "change_pct": 0.0,
        "change_abs": 0.0,
        "currency": "USD",
        "market_cap": None,
        "volume": None,
        "pe_ratio": None,
        "week_52_high": None,
        "week_52_low": None,
        "open": None,
        "prev_close": None,
        "news": [],
    }

    chart = _chart(symbol)
    meta = chart.get("meta") or {}

    if meta:
        price = float(meta.get("regularMarketPrice") or 0)

        # Extract OHLCV from chart indicators for accurate prev_close and open
        quotes_data = (chart.get("indicators") or {}).get("quote") or [{}]
        ohlcv = quotes_data[0] if quotes_data else {}
        closes = [v for v in (ohlcv.get("close") or []) if v is not None]
        opens  = [v for v in (ohlcv.get("open") or [])  if v is not None]

        # Previous close = second-to-last available close (yesterday)
        prev_close = float(closes[-2]) if len(closes) >= 2 else float(meta.get("chartPreviousClose") or 0)
        open_price = float(opens[-1]) if opens else None

        change_abs = price - prev_close if prev_close else 0.0
        change_pct = (change_abs / prev_close * 100) if prev_close else 0.0

        result.update({
            "name": meta.get("longName") or meta.get("shortName") or symbol,
            "price": round(price, 4),
            "change_abs": round(change_abs, 4),
            "change_pct": round(change_pct, 2),
            "prev_close": round(prev_close, 4) if prev_close else None,
            "currency": meta.get("currency") or "USD",
            "volume": meta.get("regularMarketVolume") or None,
            "market_cap": meta.get("marketCap") or None,
            "week_52_high": meta.get("fiftyTwoWeekHigh") or None,
            "week_52_low": meta.get("fiftyTwoWeekLow") or None,
            "open": round(open_price, 4) if open_price else None,
        })

    result["news"] = _news(symbol)
    return result
