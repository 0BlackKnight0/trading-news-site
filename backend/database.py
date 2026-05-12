# backend/database.py
import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

_client: Client | None = None

def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in environment")
        _client = create_client(url, key)
    return _client

def upsert_market(symbol: str, price: float, change_pct: float, category: str):
    get_client().table("market_cache").upsert({
        "symbol": symbol,
        "price": price,
        "change_pct": change_pct,
        "category": category,
    }, on_conflict="symbol").execute()

def get_market() -> list[dict]:
    res = get_client().table("market_cache").select("*").execute()
    return res.data

def insert_news(items: list[dict]):
    try:
        existing = {r["title"] for r in get_client().table("news_cache").select("title").execute().data}
        new_items = [i for i in items if i["title"] not in existing]
        if not new_items:
            return
        try:
            get_client().table("news_cache").insert(new_items).execute()
        except Exception:
            # Fall back without summary if column doesn't exist yet
            stripped = [{k: v for k, v in item.items() if k != "summary"} for item in new_items]
            get_client().table("news_cache").insert(stripped).execute()
    except Exception as e:
        logger.error(f"insert_news failed: {e}")

def get_news(category: str) -> list[dict]:
    res = (get_client().table("news_cache")
           .select("*")
           .eq("category", category)
           .order("published_at", desc=True)
           .limit(20)
           .execute())
    return res.data

def get_watchlist() -> list[dict]:
    return get_client().table("watchlist").select("*").execute().data

def add_to_watchlist(symbol: str, type_: str):
    get_client().table("watchlist").insert({"symbol": symbol.upper(), "type": type_}).execute()

def remove_from_watchlist(symbol: str):
    get_client().table("watchlist").delete().eq("symbol", symbol.upper()).execute()

def save_telegram_user(chat_id: int):
    get_client().table("telegram_users").upsert({"chat_id": chat_id}, on_conflict="chat_id").execute()

def get_telegram_chat_ids() -> list[int]:
    res = get_client().table("telegram_users").select("chat_id").execute()
    return [r["chat_id"] for r in res.data]
