# backend/routes/market.py
from fastapi import APIRouter

from aggregator_loop import refresh_market_if_stale
from database import get_market

router = APIRouter()

@router.get("/market")
def market():
    # No background worker on serverless — the read refreshes stale data.
    refresh_market_if_stale()
    return get_market()
