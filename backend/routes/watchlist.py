# backend/routes/watchlist.py
from fastapi import APIRouter
from pydantic import BaseModel
from database import get_watchlist, add_to_watchlist, remove_from_watchlist

router = APIRouter()

class WatchlistItem(BaseModel):
    symbol: str
    type: str

@router.get("/watchlist")
def list_watchlist():
    return get_watchlist()

@router.post("/watchlist")
def add_watchlist(item: WatchlistItem):
    add_to_watchlist(item.symbol, item.type)
    return {"status": "added", "symbol": item.symbol.upper()}

@router.delete("/watchlist/{symbol}")
def delete_watchlist(symbol: str):
    remove_from_watchlist(symbol)
    return {"status": "removed", "symbol": symbol.upper()}
