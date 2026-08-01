# backend/tests/test_telegram.py
from unittest.mock import patch


def test_format_digest():
    from telegram_bot import format_digest
    market = [
        {"symbol": "NIFTY", "price": 24832.0, "change_pct": 1.2, "category": "india"},
        {"symbol": "BTC", "price": 67420.0, "change_pct": 2.1, "category": "crypto"},
        {"symbol": "USD/INR", "price": 83.42, "change_pct": -0.2, "category": "forex"},
    ]
    trading_news = [{"title": "RBI holds rates", "source": "ET", "url": "http://et.com"}]
    tech_news = [{"title": "Nvidia AI launch", "source": "TC", "url": "http://tc.com"}]
    energy_news = [{"title": "Solar farm approved", "source": "Reuters", "url": "http://r.com"}]

    text = format_digest(market, trading_news, tech_news, energy_news)
    assert "NIFTY" in text
    assert "BTC" in text
    assert "RBI holds rates" in text
    assert "Nvidia AI launch" in text
    assert "Solar farm approved" in text

def test_format_digest_sections_present():
    from telegram_bot import format_digest
    text = format_digest([], [], [], [])
    assert "MARKETS" in text
    assert "TRADING" in text
    assert "TECH" in text
    assert "ENERGY" in text

def test_format_digest_arrow_direction():
    from telegram_bot import format_digest
    market = [
        {"symbol": "UP", "price": 100.0, "change_pct": 1.5, "category": "india"},
        {"symbol": "DOWN", "price": 100.0, "change_pct": -1.5, "category": "crypto"},
    ]
    text = format_digest(market, [], [], [])
    # UP should have ▲, DOWN should have ▼
    lines = text.split("\n")
    up_line = next((l for l in lines if "UP" in l), "")
    down_line = next((l for l in lines if "DOWN" in l), "")
    assert "▲" in up_line
    assert "▼" in down_line


# --- Webhook update handling ----------------------------------------------

def test_handle_update_registers_on_start():
    import telegram_bot
    update = {"message": {"chat": {"id": 4242}, "text": "/start"}}
    with patch("database.save_telegram_user") as save, \
         patch.object(telegram_bot, "send_message") as send:
        telegram_bot.handle_update(update)
    save.assert_called_once_with(4242)
    send.assert_called_once()

def test_handle_update_accepts_group_style_command():
    """In groups Telegram sends '/start@botname'."""
    import telegram_bot
    update = {"message": {"chat": {"id": 7}, "text": "/start@mybot"}}
    with patch("database.save_telegram_user") as save, \
         patch.object(telegram_bot, "send_message"):
        telegram_bot.handle_update(update)
    save.assert_called_once_with(7)

def test_handle_update_ignores_other_commands():
    import telegram_bot
    update = {"message": {"chat": {"id": 9}, "text": "hello there"}}
    with patch("database.save_telegram_user") as save, \
         patch.object(telegram_bot, "send_message"):
        telegram_bot.handle_update(update)
    save.assert_not_called()

def test_handle_update_ignores_updates_without_message():
    import telegram_bot
    with patch("database.save_telegram_user") as save:
        telegram_bot.handle_update({"edited_message": {}})
        telegram_bot.handle_update({})
    save.assert_not_called()

def test_send_digest_noop_without_token(monkeypatch):
    import telegram_bot
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert telegram_bot.send_digest() == 0
