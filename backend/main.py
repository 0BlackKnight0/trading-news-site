# backend/main.py
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.market import router as market_router
from routes.news import router as news_router
from routes.watchlist import router as watchlist_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Scheduler and aggregator started in Task 8
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
