# backend/routes/admin.py
from fastapi import APIRouter
from aggregator_loop import run_market_refresh, run_news_refresh
from database import get_market, get_news

router = APIRouter(prefix="/admin")

@router.post("/refresh")
def force_refresh():
    """Manually trigger market + news refresh. Returns counts after refresh."""
    market_error = None
    news_error = None

    try:
        run_market_refresh()
    except Exception as e:
        market_error = str(e)

    try:
        run_news_refresh()
    except Exception as e:
        news_error = str(e)

    market = get_market()
    trading = get_news("trading")
    tech = get_news("tech")
    energy = get_news("energy")

    return {
        "market_count": len(market),
        "news_count": {"trading": len(trading), "tech": len(tech), "energy": len(energy)},
        "market_error": market_error,
        "news_error": news_error,
        "market_sample": market[:2] if market else [],
    }
