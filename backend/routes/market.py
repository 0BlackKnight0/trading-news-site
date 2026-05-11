# backend/routes/market.py
from fastapi import APIRouter
from database import get_market

router = APIRouter()

@router.get("/market")
def market():
    return get_market()
