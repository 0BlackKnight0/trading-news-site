# backend/routes/telegram.py
"""Telegram webhook.

Replaces long-polling, which cannot run on serverless. Register it once with:

    curl -F "url=https://<api-host>/telegram/webhook" \
         -F "secret_token=$TELEGRAM_WEBHOOK_SECRET" \
         https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook
"""
import logging
import os

from fastapi import APIRouter, Header, HTTPException, Request

from telegram_bot import handle_update

router = APIRouter(prefix="/telegram")
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if secret and x_telegram_bot_api_secret_token != secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    try:
        handle_update(update)
    except Exception as e:
        # Always 200 back to Telegram, otherwise it retries the same update.
        logger.error(f"telegram update failed: {e}")

    return {"ok": True}
