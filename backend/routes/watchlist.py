# backend/routes/watchlist.py
import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel

from database import add_to_watchlist, get_watchlist_quotes, remove_from_watchlist
from identity import current_user
from pipeline import refresh_symbol

router = APIRouter()
logger = logging.getLogger(__name__)


class WatchlistItem(BaseModel):
    symbol: str
    type: str


@router.get("/watchlist")
def list_watchlist(user: dict = Depends(current_user)):
    return get_watchlist_quotes(user["id"])


def _backfill(symbol: str) -> None:
    """Best-effort: a slow or failing Yahoo call must never surface to the
    caller — the row already exists, its price just waits for the next
    scheduled refresh instead."""
    try:
        refresh_symbol(symbol)
    except Exception as e:
        logger.error(f"backfill failed for {symbol}: {e}")


@router.post("/watchlist")
def add_watchlist(item: WatchlistItem, background_tasks: BackgroundTasks,
                   user: dict = Depends(current_user)):
    symbol = item.symbol.upper()
    add_to_watchlist(user["id"], symbol, item.type)
    # Signals refresh only picks up a new symbol once the GLOBAL staleness
    # window next expires — up to SIGNALS_TTL regardless of when this symbol
    # was added, since staleness is tracked once for every symbol, not per
    # symbol. Without this, a freshly added row reads "no data yet" for as
    # long as 15 minutes, which looks exactly like adding did nothing.
    #
    # Runs after the response is sent rather than inline: refresh_symbol
    # makes a real Yahoo round trip, and putting that in the request's
    # critical path measurably slowed this endpoint and made it more likely
    # for the client's own immediate follow-up GET /watchlist to race or
    # fail against a still-busy connection.
    background_tasks.add_task(_backfill, symbol)
    return {"status": "added", "symbol": symbol}


@router.delete("/watchlist/{symbol}")
def delete_watchlist(symbol: str, user: dict = Depends(current_user)):
    remove_from_watchlist(user["id"], symbol.upper())
    return {"status": "removed", "symbol": symbol.upper()}
