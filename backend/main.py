# backend/main.py
import asyncio
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.market import router as market_router
from routes.news import router as news_router
from routes.watchlist import router as watchlist_router
from routes.admin import router as admin_router

load_dotenv()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from aggregator_loop import run_market_refresh, run_news_refresh
    from scheduler import create_scheduler
    from telegram_bot import create_application

    # Start APScheduler
    scheduler = create_scheduler()
    scheduler.start()

    # Start Telegram bot polling (no-op if token not set)
    tg_app = create_application()
    if tg_app:
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.updater.start_polling()

    # Start background aggregator loops
    async def market_loop():
        while True:
            try:
                run_market_refresh()
            except Exception as e:
                logger.error(f"Market refresh error: {e}")
            await asyncio.sleep(900)

    async def news_loop():
        while True:
            try:
                run_news_refresh()
            except Exception as e:
                logger.error(f"News refresh error: {e}")
            await asyncio.sleep(1800)

    asyncio.create_task(market_loop())
    asyncio.create_task(news_loop())

    yield

    # Graceful shutdown
    scheduler.shutdown(wait=False)
    if tg_app:
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()

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
app.include_router(admin_router)

@app.get("/health")
def health():
    return {"status": "ok"}
