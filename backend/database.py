# backend/database.py
import os
import logging
from datetime import datetime, timezone

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

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def upsert_market(symbol: str, price: float, change_pct: float, category: str):
    get_client().table("market_cache").upsert({
        "symbol": symbol,
        "price": price,
        "change_pct": change_pct,
        "category": category,
        # DEFAULT now() only fires on INSERT, so stamp it explicitly for updates.
        "updated_at": _now_iso(),
    }, on_conflict="symbol").execute()

def get_market() -> list[dict]:
    res = get_client().table("market_cache").select("*").execute()
    return res.data

def insert_news(items: list[dict]):
    try:
        existing_rows = get_client().table("news_cache").select("title, summary").execute().data
        existing_titles = {r["title"] for r in existing_rows}
        needs_summary = {r["title"] for r in existing_rows if not r.get("summary")}

        new_items = [i for i in items if i["title"] not in existing_titles]
        if new_items:
            try:
                get_client().table("news_cache").insert(new_items).execute()
            except Exception:
                stripped = [{k: v for k, v in item.items() if k != "summary"} for item in new_items]
                get_client().table("news_cache").insert(stripped).execute()

        # Backfill summaries for existing articles that have none
        for item in items:
            if item.get("summary") and item["title"] in needs_summary:
                try:
                    (get_client().table("news_cache")
                     .update({"summary": item["summary"]})
                     .eq("title", item["title"])
                     .execute())
                except Exception:
                    pass
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


# --- Refresh bookkeeping -------------------------------------------------
# Serverless has no background loop, so each read decides whether the cache
# is stale. These track when each feed was last successfully refreshed.

def mark_refreshed(key: str):
    try:
        get_client().table("refresh_meta").upsert(
            {"key": key, "updated_at": _now_iso()}, on_conflict="key"
        ).execute()
    except Exception as e:
        logger.error(f"mark_refreshed({key}) failed: {e}")

def seconds_since_refresh(key: str) -> float | None:
    """Seconds since `key` was last refreshed, or None if never / unknown."""
    try:
        res = (get_client().table("refresh_meta")
               .select("updated_at")
               .eq("key", key)
               .limit(1)
               .execute())
        if not res.data:
            return None
        stamp = res.data[0].get("updated_at")
        if not stamp:
            return None
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - parsed).total_seconds()
    except Exception as e:
        logger.error(f"seconds_since_refresh({key}) failed: {e}")
        return None
