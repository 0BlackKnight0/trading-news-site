# backend/pipeline.py
"""Wires the pure signal code to I/O.

This is the only module that both talks to the database and calls the
detectors, which is what lets everything under `signals/` stay pure.

Every write is idempotent, so a duplicated cron invocation or an overlapping
on-read refresh is harmless and the work is resumable after a timeout.
"""
import logging

from aggregator.yahoo import fetch_bars, fetch_symbol_name
from database import (
    get_snapshots,
    get_symbol_names,
    upsert_events,
    upsert_snapshots,
    upsert_symbol_name,
    upsert_symbol_stats,
)
from signals.detect import detect
from signals.stats import compute_stats

logger = logging.getLogger(__name__)

FETCH_RANGE = "3mo"
HISTORY_LIMIT = 260


def refresh_symbol(symbol: str, min_move_pct: float | None = None) -> dict:
    """Fetch, persist, recompute and detect for one symbol."""
    bars = fetch_bars(symbol, range_=FETCH_RANGE)
    if len(bars) < 2:
        logger.info(f"{symbol}: too few bars ({len(bars)}), skipping")
        return {"symbol": symbol, "bars": len(bars), "events": 0}

    upsert_snapshots(symbol, bars)
    history = get_snapshots(symbol, limit=HISTORY_LIMIT)
    if len(history) < 2:
        return {"symbol": symbol, "bars": len(bars), "events": 0}

    # The last bar is the in-progress trading day. Statistics are computed
    # from completed bars only; the detectors compare it against them.
    stats = compute_stats(history[:-1])
    upsert_symbol_stats(symbol, stats)

    events = detect(symbol, history[-1], history[-2], stats, min_move_pct, history_len=len(history))
    upsert_events(events)

    return {"symbol": symbol, "bars": len(bars), "events": len(events)}


def _ensure_symbol_names(symbols: list[str]) -> None:
    """Store a display name for any symbol that doesn't have one yet.

    News-to-symbol matching needs a company name ("Reliance", not
    "RELIANCE.NS") — see aggregator/matching.py. Names essentially never
    change, so this only costs a Yahoo call the first time a symbol is seen,
    not on every refresh.
    """
    existing = get_symbol_names()
    for symbol in symbols:
        if symbol in existing:
            continue
        name = fetch_symbol_name(symbol)
        if name:
            upsert_symbol_name(symbol, name)


def refresh_all(symbols: list[str]) -> dict:
    """Refresh many symbols. One failure never stops the rest."""
    _ensure_symbol_names(symbols)
    ok, total_events = 0, 0
    for symbol in symbols:
        try:
            result = refresh_symbol(symbol)
            ok += 1
            total_events += result["events"]
        except Exception as e:
            logger.error(f"refresh failed for {symbol}: {e}")
    return {"symbols": ok, "events": total_events}
