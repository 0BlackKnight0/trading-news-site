# backend/scripts/backfill.py
"""Seed one year of daily bars.

Without history there are no statistics, therefore no detectors, therefore an
empty feed — and nothing for the Rewind scrubber to move through. Run this
once per symbol; it is idempotent on (symbol, ts) so re-running is free.

Usage:
    ./venv/bin/python -m scripts.backfill              # every watched symbol
    ./venv/bin/python -m scripts.backfill RELIANCE.NS  # specific symbols
"""
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

from aggregator.yahoo import fetch_bars           # noqa: E402
from database import get_all_watched_symbols, upsert_snapshots  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill")

BACKFILL_RANGE = "1y"


def backfill(symbols: list[str]) -> int:
    total = 0
    for symbol in symbols:
        try:
            bars = fetch_bars(symbol, range_=BACKFILL_RANGE)
            written = upsert_snapshots(symbol, bars)
            total += written
            logger.info(f"{symbol}: {written} bars")
        except Exception as e:
            logger.error(f"{symbol}: FAILED — {e}")
    return total


def main():
    symbols = sys.argv[1:] or get_all_watched_symbols()
    if not symbols:
        logger.info("No symbols to backfill.")
        return
    logger.info(f"Backfilling {len(symbols)} symbol(s)...")
    logger.info(f"Done. {backfill(symbols)} bars written.")


if __name__ == "__main__":
    main()
