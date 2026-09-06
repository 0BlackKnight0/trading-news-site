# backend/main.py
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.admin import router as admin_router
from routes.cron import router as cron_router
from routes.feed import router as feed_router
from routes.history import router as history_router
from routes.market import router as market_router
from routes.news import router as news_router
from routes.search import router as search_router
from routes.telegram import router as telegram_router
from routes.ticker import router as ticker_router
from routes.watchlist import router as watchlist_router

load_dotenv()

# Each request is a short-lived serverless invocation: no scheduler, no
# polling, no background loops. Cache refresh happens on read (see
# aggregator_loop) and the daily digest is driven by Vercel Cron.
app = FastAPI(title="Trading Dashboard API")

_origins = os.environ.get("CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market_router)
app.include_router(news_router)
app.include_router(watchlist_router)
app.include_router(admin_router)
app.include_router(search_router)
app.include_router(ticker_router)
app.include_router(cron_router)
app.include_router(telegram_router)
app.include_router(feed_router)
app.include_router(history_router)


@app.get("/health")
def health():
    return {"status": "ok"}
