# backend/aggregator/market.py
import requests
import yfinance as yf

try:
    from nsepython import nse_eq, nse_index
    NSE_AVAILABLE = True
except Exception:
    NSE_AVAILABLE = False

CRYPTO_IDS = "bitcoin,ethereum,solana,binancecoin,ripple,cardano,polkadot,dogecoin,avalanche-2,chainlink"
FOREX_PAIRS = {
    "USD/INR": "USDINR=X",
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "EUR/INR": "EURINR=X",
}


def fetch_india() -> list[dict]:
    results = []
    indices = [
        ("NIFTY", "NIFTY 50"),
        ("SENSEX", "SENSEX"),
        ("BANKNIFTY", "NIFTY BANK"),
    ]
    for symbol, index_name in indices:
        try:
            if NSE_AVAILABLE:
                data = nse_index(index_name)
                price = float(data.get("last", 0))
                change_pct = float(data.get("percentChange", 0))
            else:
                yf_symbol = {"NIFTY": "^NSEI", "SENSEX": "^BSESN", "BANKNIFTY": "^NSEBANK"}.get(symbol, "^NSEI")
                ticker = yf.Ticker(yf_symbol)
                info = ticker.info
                price = info.get("regularMarketPrice", 0)
                change_pct = info.get("regularMarketChangePercent", 0)
            results.append({
                "symbol": symbol,
                "price": price,
                "change_pct": round(change_pct, 2),
                "category": "india",
            })
        except Exception:
            pass
    return results


def fetch_crypto() -> list[dict]:
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={CRYPTO_IDS}&order=market_cap_desc&per_page=10&page=1"
    )
    try:
        resp = requests.get(url, timeout=10)
        items = resp.json()
        return [
            {
                "symbol": item["symbol"].upper(),
                "price": item["current_price"],
                "change_pct": round(item.get("price_change_percentage_24h", 0), 2),
                "category": "crypto",
            }
            for item in items
        ]
    except Exception:
        return []


def fetch_forex() -> list[dict]:
    results = []
    for display_symbol, ticker_symbol in FOREX_PAIRS.items():
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            price = info.get("regularMarketPrice", 0)
            change_pct = info.get("regularMarketChangePercent", 0)
            results.append({
                "symbol": display_symbol,
                "price": round(price, 4),
                "change_pct": round(change_pct, 2),
                "category": "forex",
            })
        except Exception:
            pass
    return results


def fetch_all() -> list[dict]:
    return fetch_india() + fetch_crypto() + fetch_forex()
