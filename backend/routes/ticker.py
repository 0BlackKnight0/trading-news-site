# backend/routes/ticker.py
import logging
from datetime import datetime, timezone
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, Query

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_news(raw_news: list) -> list[dict]:
    news = []
    for item in (raw_news or [])[:10]:
        if not isinstance(item, dict):
            continue
        content = item.get("content") or {}
        if content:
            title = content.get("title", "")
            url_obj = content.get("canonicalUrl") or {}
            url = url_obj.get("url", "") if isinstance(url_obj, dict) else ""
            provider = content.get("provider") or {}
            source = provider.get("displayName", "") if isinstance(provider, dict) else ""
            pub = content.get("pubDate", "")
            summary = content.get("summary", "") or ""
        else:
            title = item.get("title", "")
            url = item.get("link", "")
            source = item.get("publisher", "")
            ts = item.get("providerPublishTime")
            pub = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else ""
            summary = ""
        if title:
            news.append({"title": title, "url": url, "source": source, "published_at": pub, "summary": summary})
    return news


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

    ticker = yf.Ticker(symbol)

    # 1. Primary price source: history() — far more reliable than info/fast_info
    try:
        hist = ticker.history(period="5d", auto_adjust=True)
        if not hist.empty:
            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) >= 2 else None
            price = float(latest["Close"])
            prev_close = float(prev["Close"]) if prev is not None else None
            change_abs = price - (prev_close or price)
            change_pct = (change_abs / prev_close * 100) if prev_close else 0.0
            vol = latest.get("Volume")
            open_p = latest.get("Open")
            result.update({
                "price": round(price, 4),
                "change_abs": round(change_abs, 4),
                "change_pct": round(change_pct, 2),
                "prev_close": round(prev_close, 4) if prev_close else None,
                "volume": int(vol) if vol and not pd.isna(vol) else None,
                "open": round(float(open_p), 4) if open_p and not pd.isna(open_p) else None,
            })
    except Exception as e:
        logger.error(f"history() failed for {symbol}: {e}")

    # 2. 52-week high/low from 1-year daily history
    try:
        hist_1y = ticker.history(period="1y", auto_adjust=True)
        if not hist_1y.empty:
            result["week_52_high"] = round(float(hist_1y["High"].max()), 2)
            result["week_52_low"] = round(float(hist_1y["Low"].min()), 2)
    except Exception:
        pass

    # 3. fast_info for market cap (supplementary)
    try:
        fast = ticker.fast_info
        mc = getattr(fast, "market_cap", None)
        if mc and mc > 0:
            result["market_cap"] = int(mc)
    except Exception:
        pass

    # 4. info for name, currency, P/E, market cap fallback
    try:
        info = ticker.info or {}
        name = info.get("longName") or info.get("shortName") or info.get("displayName")
        if name:
            result["name"] = name
        result["currency"] = info.get("currency") or "USD"
        pe = info.get("trailingPE")
        if pe and float(pe) > 0:
            result["pe_ratio"] = round(float(pe), 2)
        if not result["market_cap"]:
            mc = info.get("marketCap")
            if mc:
                result["market_cap"] = int(mc)
    except Exception:
        pass

    # 5. News from yfinance
    try:
        result["news"] = _parse_news(ticker.news)
    except Exception:
        pass

    return result
