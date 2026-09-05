# backend/routes/feed.py
"""The changelog.

`GET /feed` is the whole product: events newest-first, plus the count of
those the caller has not seen. The divider the UI draws sits at
`last_seen_at`.
"""
from fastapi import APIRouter, Depends, Query

from database import count_events_since, get_events, get_last_seen, set_last_seen
from identity import current_user

router = APIRouter()

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@router.get("/feed")
def feed(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    cursor: str | None = Query(default=None),
    since: str | None = Query(default=None),
    user: dict = Depends(current_user),
):
    # `since` lets the client re-anchor the divider ("show me this week");
    # by default the baseline is where the user actually stopped reading.
    baseline = since or get_last_seen(user["id"])
    events = get_events(before=cursor, limit=limit)
    return {
        "events": events,
        "unread_count": count_events_since(baseline),
        "last_seen_at": baseline,
        "next_cursor": events[-1]["occurred_at"] if len(events) == limit else None,
    }


@router.post("/feed/seen")
def seen(user: dict = Depends(current_user)):
    """Catch up — move the divider to now."""
    return {"last_seen_at": set_last_seen(user["id"])}
