# backend/main.py
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.market import router as market_router
from routes.news import router as news_router
from routes.watchlist import router as watchlist_router
import logging

logger = logging.getLogger(__name__)

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    from aggregator_loop import run_market_refresh, run_news_refresh

    async def market_loop():
        while True:
            try:
                run_market_refresh()
            except Exception as e:
                logger.error(f"Market refresh error: {e}")
            await asyncio.sleep(900)  # 15 minutes

    async def news_loop():
        while True:
            try:
                run_news_refresh()
            except Exception as e:
                logger.error(f"News refresh error: {e}")
            await asyncio.sleep(1800)  # 30 minutes

    asyncio.create_task(market_loop())
    asyncio.create_task(news_loop())
    yield

app = FastAPI(title="Trading Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market_router)
app.include_router(news_router)
app.include_router(watchlist_router)

@app.get("/health")
def health():
    return {"status": "ok"}
