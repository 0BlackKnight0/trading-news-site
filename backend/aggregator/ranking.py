# backend/aggregator/ranking.py
"""Article scoring — deliberately a handful of integers, not a model.

Same philosophy as the signal detectors: every point is attributable to a
named rule, so a ranking can be explained and tuned rather than trusted.

Pure by contract: `now` is passed in, never read from the clock.
"""
import re
from datetime import datetime, timezone

# Tier 3: wire services and major market desks. Tier 2: known specialist
# outlets. Everything unlisted scores 1.
SOURCE_WEIGHTS = {
    "reuters": 3, "associated press": 3, "bloomberg": 3, "cnbc": 3,
    "financial times": 3, "economic times": 3, "business standard": 3,
    "moneycontrol": 3, "businessline": 3, "the wall street journal": 3,
    "techcrunch ai": 2, "mit tech review": 2, "the verge ai": 2,
    "scmp tech": 2, "oilprice.com": 2, "cleantechnica": 2, "wired": 2,
    "ars technica": 2, "the information": 2,
}

SYMBOL_BONUS = 2
_TITLE_KEY_LENGTH = 60


def source_weight(source: str) -> int:
    return SOURCE_WEIGHTS.get((source or "").lower().strip(), 1)


def recency_bucket(published_at: str | None, now: str) -> int:
    if not published_at:
        return 0
    try:
        then = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        current = datetime.fromisoformat(now.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    hours = (current - then).total_seconds() / 3600
    if hours < 2:
        return 3
    if hours < 12:
        return 2
    if hours < 48:
        return 1
    return 0


def score_article(item: dict, now: str, corroboration: int = 0) -> int:
    return (
        source_weight(item.get("source", ""))
        + (SYMBOL_BONUS if item.get("symbol") else 0)
        + recency_bucket(item.get("published_at"), now)
        + corroboration
    )


def _title_key(title: str) -> str:
    """Normalise conservatively — this only ever adds a point, so a rare
    mis-group is cheap, while an aggressive normaliser merging distinct
    stories would not be."""
    stripped = re.sub(r"[^a-z0-9 ]", "", (title or "").lower())
    return " ".join(stripped.split())[:_TITLE_KEY_LENGTH]


def apply_scores(items: list[dict], now: str) -> list[dict]:
    """Score every item, crediting corroboration within this batch.

    Corroboration counts DISTINCT sources telling the same story, so one
    outlet republishing itself earns nothing.
    """
    sources_by_key: dict[str, set[str]] = {}
    for item in items:
        key = _title_key(item.get("title", ""))
        sources_by_key.setdefault(key, set()).add((item.get("source") or "").lower())

    for item in items:
        key = _title_key(item.get("title", ""))
        corroboration = max(0, len(sources_by_key.get(key, set())) - 1)
        item["score"] = score_article(item, now, corroboration)
    return items
