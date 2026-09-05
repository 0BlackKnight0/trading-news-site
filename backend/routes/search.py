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

RESULT_LIMIT = 7
DEFAULT_QUOTES_COUNT = 8
# Fetched instead of the default when a type filter is active. Yahoo's top
# matches for a plain query skew toward one instrument type — a bare ticker
# mostly returns stocks — so filtering the default top 8 down to "crypto"
# would often yield nothing. Asking for more candidates up front is what
# lets the filter actually surface matches of the requested type.
WIDE_QUOTES_COUNT = 25


def _map_quote(item: dict) -> dict | None:
    """Map one raw Yahoo quote to our SearchResult shape, or None if its
    instrument type isn't one we support."""
    mapped = _TYPE_MAP.get(item.get("quoteType", ""))
    if not mapped:
        return None
    symbol = item.get("symbol", "")
    name = item.get("shortname") or item.get("longname") or symbol
    exchange = item.get("exchDisp") or item.get("exchange", "")
    return {"symbol": symbol, "name": name, "exchange": exchange, "type": mapped}


@router.get("/search")
def search(
    q: str = Query(min_length=1),
    type: str | None = Query(default=None, enum=["stock", "crypto", "forex"]),
):
    try:
        quotes_count = WIDE_QUOTES_COUNT if type else DEFAULT_QUOTES_COUNT
        url = (
            "https://query2.finance.yahoo.com/v1/finance/search"
            f"?q={q}&quotesCount={quotes_count}&newsCount=0"
            "&enableFuzzyQuery=false&listsCount=0"
        )
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        resp = requests.get(url, headers=headers, timeout=5)
        quotes = resp.json().get("quotes", [])

        results = [r for item in quotes if (r := _map_quote(item)) is not None]
        if type:
            results = [r for r in results if r["type"] == type]
        return results[:RESULT_LIMIT]
    except Exception:
        return []
