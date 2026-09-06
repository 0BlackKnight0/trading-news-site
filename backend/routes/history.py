# backend/routes/history.py
"""Rewind: replay one symbol's own chart from the user's last visit to now.

Scoped to a single symbol per request, not the whole board — selecting a
symbol reveals its own scrubber; nothing else on the sidebar re-renders.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from database import get_last_seen, get_snapshot_range, get_watchlist
from identity import current_user

router = APIRouter()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/history")
def history(
    symbol: str = Query(...),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    user: dict = Depends(current_user),
):
    symbol = symbol.upper()
    watched = {row["symbol"] for row in get_watchlist(user["id"])}
    if symbol not in watched:
        raise HTTPException(status_code=404, detail="Symbol not on your watchlist")

    last_seen_at = get_last_seen(user["id"])
    # The scrubbable range defaults to "since you last checked" — a replay
    # of your absence, not an arbitrary date-range chart.
    range_from = from_ or last_seen_at
    range_to = to or _utc_now_iso()
    bars = get_snapshot_range(symbol, range_from, range_to)
    return {"symbol": symbol, "last_seen_at": last_seen_at, "bars": bars}
