# backend/routes/search.py
import requests
from fastapi import APIRouter, Query

router = APIRouter()

_TYPE_MAP = {
    "EQUITY": "stock",
    "ETF": "stock",
    "MUTUALFUND": "stock",
    "CRYPTOCURRENCY": "crypto",
    "CURRENCY": "forex",
}

@router.get("/search")
def search(q: str = Query(min_length=1)):
    try:
        url = (
            "https://query2.finance.yahoo.com/v1/finance/search"
            f"?q={q}&quotesCount=8&newsCount=0&enableFuzzyQuery=false&listsCount=0"
        )
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        resp = requests.get(url, headers=headers, timeout=5)
        quotes = resp.json().get("quotes", [])
        results = []
        for item in quotes:
            qtype = item.get("quoteType", "")
            mapped = _TYPE_MAP.get(qtype)
            if not mapped:
                continue
            symbol = item.get("symbol", "")
            name = item.get("shortname") or item.get("longname") or symbol
            exchange = item.get("exchDisp") or item.get("exchange", "")
            results.append({"symbol": symbol, "name": name, "exchange": exchange, "type": mapped})
        return results[:7]
    except Exception:
        return []
