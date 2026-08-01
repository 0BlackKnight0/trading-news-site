# backend/aggregator/market.py
import requests

from aggregator.yahoo import fetch_quotes

CRYPTO_IDS = "bitcoin,ethereum,solana,binancecoin,ripple,cardano,polkadot,dogecoin,avalanche-2,chainlink"
CRYPTO_LIMIT = 10
HTTP_TIMEOUT = 10

INDIA_SYMBOLS = {
    "NIFTY": "^NSEI",
    "SENSEX": "^BSESN",
    "BANKNIFTY": "^NSEBANK",
}
FOREX_PAIRS = {
    "USD/INR": "USDINR=X",
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "EUR/INR": "EURINR=X",
}
GLOBAL_SYMBOLS = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW": "^DJI",
    "GOLD": "GC=F",
    "OIL": "CL=F",
}


def _fetch_group(mapping: dict[str, str], category: str, price_digits: int) -> list[dict]:
    """Fetch a display-name -> yahoo-symbol mapping as market_cache rows."""
    quotes = fetch_quotes(list(mapping.values()))
    results = []
    for display_symbol, yahoo_symbol in mapping.items():
        quote = quotes.get(yahoo_symbol)
        if not quote:
            continue
        results.append({
            "symbol": display_symbol,
            "price": round(quote["price"], price_digits),
            "change_pct": round(quote["change_pct"], 2),
            "category": category,
        })
    return results


def fetch_india() -> list[dict]:
    return _fetch_group(INDIA_SYMBOLS, "india", 2)


def fetch_forex() -> list[dict]:
    return _fetch_group(FOREX_PAIRS, "forex", 4)


def fetch_global() -> list[dict]:
    return _fetch_group(GLOBAL_SYMBOLS, "global", 2)


def fetch_crypto() -> list[dict]:
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={CRYPTO_IDS}&order=market_cap_desc&per_page={CRYPTO_LIMIT}&page=1"
    )
    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT)
        items = resp.json()
        results = []
        for item in items:
            try:
                results.append({
                    "symbol": item["symbol"].upper(),
                    "price": item["current_price"],
                    "change_pct": round(item.get("price_change_percentage_24h", 0), 2),
                    "category": "crypto",
                })
            except Exception:
                pass
        return results
    except Exception:
        return []


def fetch_all() -> list[dict]:
    return fetch_india() + fetch_crypto() + fetch_forex() + fetch_global()
