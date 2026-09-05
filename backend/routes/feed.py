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


def _parse_cursor(cursor: str | None) -> tuple[str | None, int | None]:
    """Split the opaque `"{occurred_at}|{id}"` cursor into its two parts.

    A malformed cursor (missing separator, non-integer id, or anything else
    unexpected) must not 500 the request — it is treated as no cursor.
    """
    if not cursor:
        return None, None
    occurred_at, sep, raw_id = cursor.rpartition("|")
    if not sep:
        return None, None
    try:
        return occurred_at, int(raw_id)
    except ValueError:
        return None, None


def _make_cursor(occurred_at: str, event_id: int) -> str:
    return f"{occurred_at}|{event_id}"


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
    before_ts, before_id = _parse_cursor(cursor)
    events = get_events(before_ts=before_ts, before_id=before_id, limit=limit)
    next_cursor = (
        _make_cursor(events[-1]["occurred_at"], events[-1]["id"])
        if len(events) == limit
        else None
    )
    return {
        "events": events,
        "unread_count": count_events_since(baseline),
        "last_seen_at": baseline,
        "next_cursor": next_cursor,
    }


@router.post("/feed/seen")
def seen(user: dict = Depends(current_user)):
    """Catch up — move the divider to now."""
    return {"last_seen_at": set_last_seen(user["id"])}
