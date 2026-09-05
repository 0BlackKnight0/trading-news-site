# backend/database.py
import os
import logging
from datetime import datetime, timezone

from supabase import create_client, Client

from signals.types import Bar, DetectedEvent, SymbolStats

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

def get_watchlist(user_id: str) -> list[dict]:
    return (get_client().table("watchlist")
            .select("*").eq("user_id", user_id).execute().data)

def add_to_watchlist(user_id: str, symbol: str, type_: str):
    get_client().table("watchlist").upsert(
        {"user_id": user_id, "symbol": symbol.upper(), "type": type_},
        on_conflict="user_id,symbol",
    ).execute()

def remove_from_watchlist(user_id: str, symbol: str):
    (get_client().table("watchlist")
     .delete().eq("user_id", user_id).eq("symbol", symbol.upper()).execute())

def get_all_watched_symbols() -> list[str]:
    """Every symbol on any watchlist — the refresh pipeline's work queue."""
    rows = get_client().table("watchlist").select("symbol").execute().data or []
    return sorted({r["symbol"] for r in rows})

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


# --- The Line: snapshots, stats, events, users ---------------------------

def upsert_snapshots(symbol: str, bars: list[Bar]) -> int:
    """Persist daily bars. Idempotent on (symbol, ts)."""
    if not bars:
        return 0
    rows = [{
        "symbol": symbol, "ts": b.ts, "open": b.open, "high": b.high,
        "low": b.low, "close": b.close, "volume": b.volume, "source": "yahoo",
    } for b in bars]
    get_client().table("price_snapshots").upsert(rows, on_conflict="symbol,ts").execute()
    return len(rows)


def get_snapshots(symbol: str, limit: int = 260) -> list[Bar]:
    """The most recent `limit` bars for a symbol, returned oldest-first."""
    res = (get_client().table("price_snapshots")
           .select("ts, open, high, low, close, volume")
           .eq("symbol", symbol)
           .order("ts", desc=True)
           .limit(limit)
           .execute())
    bars = [Bar(ts=r["ts"], open=r["open"], high=r["high"], low=r["low"],
                close=float(r["close"]), volume=r["volume"])
            for r in reversed(res.data or []) if r.get("close") is not None]
    return bars


def upsert_symbol_stats(symbol: str, stats: SymbolStats) -> None:
    get_client().table("symbol_stats").upsert({
        "symbol": symbol,
        "avg_daily_range": stats.avg_daily_range,
        "avg_volume_20d": int(stats.avg_volume_20d) if stats.avg_volume_20d else None,
        "vol_30d": stats.vol_30d,
        "high_52w": stats.high_52w,
        "low_52w": stats.low_52w,
        "high_20d": stats.high_20d,
        "low_20d": stats.low_20d,
        "computed_at": _now_iso(),
    }, on_conflict="symbol").execute()


def upsert_events(events: list[DetectedEvent]) -> int:
    """Write events idempotently.

    Payload and severity are refreshed rather than ignored: the current day's
    bar is incomplete intraday, so a move detected at 10:00 can fade by close.
    `occurred_at` pins first detection and never moves.
    """
    if not events:
        return 0
    rows = [{
        "symbol": e.symbol, "kind": e.kind, "occurred_at": e.occurred_at,
        "severity": e.severity, "payload": e.payload, "dedupe_key": e.dedupe_key,
    } for e in events]
    get_client().table("events").upsert(rows, on_conflict="dedupe_key").execute()
    return len(rows)


def get_events(before_ts: str | None = None, before_id: int | None = None, limit: int = 50) -> list[dict]:
    """Events newest-first, ordered by (occurred_at, id).

    `occurred_at` is a market bar's timestamp, so every symbol on the same
    exchange session shares the exact same value — ties are the norm, not an
    edge case. Ordering (and paginating) by `occurred_at` alone lets a strict
    `.lt(occurred_at)` cursor skip an entire tied group. `id` (BIGSERIAL) is
    a total order, so (occurred_at, id) breaks ties deterministically.

    `before_ts`/`before_id` together form the cursor: rows strictly before
    that (occurred_at, id) pair, walking through a tied group rather than
    jumping over it.
    """
    query = (get_client().table("events")
             .select("*")
             .order("occurred_at", desc=True)
             .order("id", desc=True)
             .limit(limit))
    if before_ts is not None and before_id is not None:
        query = query.or_(
            f"occurred_at.lt.{before_ts},and(occurred_at.eq.{before_ts},id.lt.{before_id})"
        )
    return query.execute().data or []


def count_events_since(ts: str) -> int:
    res = (get_client().table("events")
           .select("id", count="exact")
           .gt("occurred_at", ts)
           .execute())
    return res.count or 0


def get_or_create_user(device_key: str) -> dict:
    existing = (get_client().table("users")
                .select("*").eq("device_key", device_key).limit(1).execute())
    if existing.data:
        return existing.data[0]
    created = get_client().table("users").insert({"device_key": device_key}).execute()
    user = created.data[0]
    get_client().table("user_state").upsert(
        {"user_id": user["id"], "last_seen_at": _now_iso()}, on_conflict="user_id"
    ).execute()
    return user


def get_last_seen(user_id: str) -> str:
    res = (get_client().table("user_state")
           .select("last_seen_at").eq("user_id", user_id).limit(1).execute())
    if res.data and res.data[0].get("last_seen_at"):
        return res.data[0]["last_seen_at"]
    return _now_iso()


def set_last_seen(user_id: str) -> str:
    stamp = _now_iso()
    get_client().table("user_state").upsert(
        {"user_id": user_id, "last_seen_at": stamp}, on_conflict="user_id"
    ).execute()
    return stamp


def get_watchlist_quotes(user_id: str) -> list[dict]:
    """Watchlist rows enriched with the latest stored price.

    Prices come from `price_snapshots`, not from a live fetch, so the row can
    always state honestly how old the number is. Symbols with no history yet
    report None rather than zero — unknown is not the same as worthless.
    """
    rows = get_watchlist(user_id)
    enriched = []
    for row in rows:
        bars = get_snapshots(row["symbol"], limit=2)
        price = change_pct = as_of = None
        if bars:
            price = bars[-1].close
            as_of = bars[-1].ts
            if len(bars) == 2 and bars[0].close:
                change_pct = (bars[-1].close / bars[0].close - 1) * 100
        enriched.append({**row, "price": price, "change_pct": change_pct, "as_of": as_of})
    return enriched
