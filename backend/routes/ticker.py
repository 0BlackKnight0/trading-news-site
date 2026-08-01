# backend/routes/ticker.py
import logging
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, Query

from aggregator.yahoo import HEADERS, TIMEOUT, fetch_chart, quote_from_chart

router = APIRouter()
logger = logging.getLogger(__name__)


def _news(symbol: str) -> list[dict]:
    """Fetch recent news from Yahoo Finance search API."""
    try:
        r = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": symbol, "newsCount": 8, "quotesCount": 0},
            headers=HEADERS,
            timeout=TIMEOUT,
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

    quote = quote_from_chart(fetch_chart(symbol))
    if quote:
        result.update({
            "name": quote["name"] or symbol,
            "price": round(quote["price"], 4),
            "change_abs": round(quote["change_abs"], 4),
            "change_pct": round(quote["change_pct"], 2),
            "prev_close": round(quote["prev_close"], 4) if quote["prev_close"] else None,
            "open": round(quote["open"], 4) if quote["open"] else None,
            "currency": quote["currency"],
            "volume": quote["volume"],
            "market_cap": quote["market_cap"],
            "week_52_high": quote["week_52_high"],
            "week_52_low": quote["week_52_low"],
        })

    result["news"] = _news(symbol)
    return result
