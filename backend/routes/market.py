# backend/routes/market.py
from fastapi import APIRouter

from aggregator.market import watchlist_target
from aggregator_loop import refresh_market_if_stale
from database import get_market

router = APIRouter()

@router.get("/market")
def market():
    # No background worker on serverless — the read refreshes stale data.
    refresh_market_if_stale()
    rows = get_market()
    for row in rows:
        # A display symbol ("NIFTY", "BTC") isn't Yahoo-fetchable on its
        # own — the client needs the real ticker to add this row to the
        # watchlist directly, rather than creating a row that can never
        # be backfilled.
        target = watchlist_target(row["symbol"], row["category"])
        row["watchlist_symbol"], row["watchlist_type"] = target if target else (None, None)
    return rows
