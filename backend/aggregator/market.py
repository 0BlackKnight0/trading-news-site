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
# CoinGecko's display symbol -> the Yahoo ticker the watchlist pipeline can
# actually fetch. Needed because market_cache stores CoinGecko's bare symbol
# ("BTC"), which Yahoo's chart API does not resolve on its own — it needs
# the "-USD" suffix. Covers exactly the coins CRYPTO_IDS fetches.
CRYPTO_SYMBOLS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "BNB": "BNB-USD",
    "XRP": "XRP-USD",
    "ADA": "ADA-USD",
    "DOT": "DOT-USD",
    "DOGE": "DOGE-USD",
    "AVAX": "AVAX-USD",
    "LINK": "LINK-USD",
}

# category -> (display->yahoo mapping, the WatchlistType to add it as).
# india and global both use Yahoo index/futures tickers, which the pipeline
# treats the same as any other stock-type symbol.
_WATCHLIST_TARGETS = {
    "india": (INDIA_SYMBOLS, "stock"),
    "global": (GLOBAL_SYMBOLS, "stock"),
    "forex": (FOREX_PAIRS, "forex"),
    "crypto": (CRYPTO_SYMBOLS, "crypto"),
}


# Extra news-matching aliases for symbols where nothing in the ticker or
# Yahoo's own long name predicts how headlines actually refer to them —
# "NIFTY 50" doesn't tell you "Nifty" is the common form, and nothing about
# "USDINR=X" suggests articles say "rupee". Reviewed by hand, not derived.
# Crypto and commodity-futures names don't need this: aliases_for already
# strips their trailing "USD" / rolling contract-month tokens generically.
NEWS_ALIAS_OVERRIDES = {
    "^NSEI": ["nifty"],
    "^BSESN": ["sensex"],
    "^NSEBANK": ["bank nifty", "banknifty"],
    "^IXIC": ["nasdaq"],
    "^DJI": ["dow jones", "dow"],
    "USDINR=X": ["rupee"],
    "EURINR=X": ["euro"],
    "EURUSD=X": ["euro"],
    "GBPUSD=X": ["british pound"],
    # Bare "gold" is denylisted as an ambiguous alias (see matching.py) after
    # being caught tagging a "gold mine" idiom and a literal color
    # description live in production. "gold price" is narrower and misses
    # some genuine coverage (a central-bank-reserves story, for instance)
    # in exchange for never matching those false positives.
    "GC=F": ["gold price"],
}


def watchlist_target(symbol: str, category: str) -> tuple[str, str] | None:
    """The (yahoo_symbol, watchlist_type) to add for a market_cache row, or
    None if this symbol can't be added directly (unknown category, or a
    display symbol market_cache doesn't actually populate for it).

    Display symbols ("NIFTY", "BTC", "USD/INR") are not Yahoo-fetchable on
    their own — adding them to the watchlist as-is would create a row that
    can never be backfilled and would sit at "no data yet" forever.
    """
    entry = _WATCHLIST_TARGETS.get(category)
    if not entry:
        return None
    mapping, watchlist_type = entry
    yahoo_symbol = mapping.get(symbol)
    return (yahoo_symbol, watchlist_type) if yahoo_symbol else None


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
