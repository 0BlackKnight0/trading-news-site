# backend/routes/ticker.py
from datetime import datetime, timezone
import yfinance as yf
from fastapi import APIRouter, Query

router = APIRouter()


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

    try:
        ticker = yf.Ticker(symbol)

        # fast_info for price (quick)
        try:
            fast = ticker.fast_info
            price = float(getattr(fast, "last_price", 0) or 0)
            prev_close = float(getattr(fast, "previous_close", 0) or 0)
            change_abs = price - prev_close if price and prev_close else 0.0
            change_pct = (change_abs / prev_close * 100) if prev_close else 0.0
            market_cap = getattr(fast, "market_cap", None)
            result.update({
                "price": round(price, 4),
                "change_abs": round(change_abs, 4),
                "change_pct": round(change_pct, 2),
                "prev_close": round(prev_close, 4) if prev_close else None,
                "market_cap": int(market_cap) if market_cap else None,
            })
        except Exception:
            pass

        # info for richer stats
        try:
            info = ticker.info or {}
            result["name"] = info.get("longName") or info.get("shortName") or symbol
            result["currency"] = info.get("currency", "USD") or "USD"
            result["volume"] = info.get("regularMarketVolume") or info.get("volume")
            pe = info.get("trailingPE")
            result["pe_ratio"] = round(float(pe), 2) if pe else None
            result["week_52_high"] = info.get("fiftyTwoWeekHigh")
            result["week_52_low"] = info.get("fiftyTwoWeekLow")
            result["open"] = info.get("regularMarketOpen")
            if not result["price"]:
                result["price"] = float(info.get("regularMarketPrice") or 0)
            if not result["market_cap"]:
                mc = info.get("marketCap")
                result["market_cap"] = int(mc) if mc else None
        except Exception:
            pass

        # news
        try:
            result["news"] = _parse_news(ticker.news)
        except Exception:
            pass

    except Exception as e:
        result["error"] = str(e)

    return result
