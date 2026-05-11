# backend/tests/test_telegram.py

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
