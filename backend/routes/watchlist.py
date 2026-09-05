# backend/routes/watchlist.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from database import add_to_watchlist, get_watchlist, remove_from_watchlist
from identity import current_user

router = APIRouter()


class WatchlistItem(BaseModel):
    symbol: str
    type: str


@router.get("/watchlist")
def list_watchlist(user: dict = Depends(current_user)):
    return get_watchlist(user["id"])


@router.post("/watchlist")
def add_watchlist(item: WatchlistItem, user: dict = Depends(current_user)):
    add_to_watchlist(user["id"], item.symbol.upper(), item.type)
    return {"status": "added", "symbol": item.symbol.upper()}


@router.delete("/watchlist/{symbol}")
def delete_watchlist(symbol: str, user: dict = Depends(current_user)):
    remove_from_watchlist(user["id"], symbol.upper())
    return {"status": "removed", "symbol": symbol.upper()}
