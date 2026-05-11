# backend/scheduler.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram_bot import send_digest

logger = logging.getLogger(__name__)

def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        send_digest,
        CronTrigger(hour=8, minute=0, timezone="Asia/Kolkata"),
        id="morning_digest",
        replace_existing=True,
    )
    logger.info("Scheduler created: digest fires at 08:00 IST daily")
    return scheduler
