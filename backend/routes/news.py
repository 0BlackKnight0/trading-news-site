# backend/routes/news.py
from fastapi import APIRouter, Query
from database import get_news

router = APIRouter()

@router.get("/news")
def news(category: str = Query(default="trading", enum=["trading", "tech", "energy"])):
    return get_news(category)
