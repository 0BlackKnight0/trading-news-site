# backend/tests/test_feed_routes.py
from unittest.mock import patch

from fastapi.testclient import TestClient

from identity import MIN_KEY_LENGTH, current_user
from main import app

client = TestClient(app)
HEADERS = {"X-Device-Key": "k" * MIN_KEY_LENGTH}

EVENT = {
    "id": 1, "symbol": "RELIANCE", "kind": "RANGE_BREAK",
    "occurred_at": "2026-03-04T10:00:00+00:00", "severity": 3,
    "payload": {"scope": "52w", "direction": "high"},
    "dedupe_key": "RELIANCE|RANGE_BREAK|2026-03-04",
}


def _as_user(user_id="u1"):
    app.dependency_overrides[current_user] = lambda: {"id": user_id}


def teardown_function():
    app.dependency_overrides.clear()


def test_feed_requires_a_device_key():
    resp = client.get("/feed")
    assert resp.status_code == 401


def test_feed_returns_events_with_an_unread_count():
    _as_user()
    with patch("routes.feed.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.feed.get_events", return_value=[EVENT]), \
         patch("routes.feed.count_events_since", return_value=7):
        resp = client.get("/feed", headers=HEADERS)
    body = resp.json()
    assert resp.status_code == 200
    assert body["unread_count"] == 7
    assert body["events"][0]["symbol"] == "RELIANCE"
    assert body["last_seen_at"] == "2026-03-01T00:00:00+00:00"


def test_unread_is_counted_against_the_users_last_visit():
    _as_user()
    with patch("routes.feed.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.feed.get_events", return_value=[]), \
         patch("routes.feed.count_events_since") as counter:
        client.get("/feed", headers=HEADERS)
    counter.assert_called_once_with("2026-03-01T00:00:00+00:00")


def test_since_overrides_the_divider_baseline():
    _as_user()
    with patch("routes.feed.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.feed.get_events", return_value=[]), \
         patch("routes.feed.count_events_since") as counter:
        client.get("/feed?since=2026-02-01T00:00:00%2B00:00", headers=HEADERS)
    counter.assert_called_once_with("2026-02-01T00:00:00+00:00")


def test_next_cursor_is_null_on_a_short_page():
    _as_user()
    with patch("routes.feed.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.feed.get_events", return_value=[EVENT]), \
         patch("routes.feed.count_events_since", return_value=0):
        body = client.get("/feed?limit=50", headers=HEADERS).json()
    assert body["next_cursor"] is None


def test_next_cursor_is_set_on_a_full_page():
    _as_user()
    with patch("routes.feed.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.feed.get_events", return_value=[EVENT]), \
         patch("routes.feed.count_events_since", return_value=0):
        body = client.get("/feed?limit=1", headers=HEADERS).json()
    # Repointed for the composite (occurred_at, id) cursor: occurred_at alone
    # ties across same-session events, so the cursor now carries the event id
    # too. Was: assert body["next_cursor"] == "2026-03-04T10:00:00+00:00"
    assert body["next_cursor"] == "2026-03-04T10:00:00+00:00|1"


def test_next_cursor_is_the_composite_form():
    """next_cursor on a full page must carry both occurred_at and id, since
    occurred_at alone ties across every symbol in the same session's bar."""
    _as_user()
    with patch("routes.feed.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.feed.get_events", return_value=[EVENT]), \
         patch("routes.feed.count_events_since", return_value=0):
        body = client.get("/feed?limit=1", headers=HEADERS).json()
    occurred_at, sep, event_id = body["next_cursor"].rpartition("|")
    assert sep == "|"
    assert occurred_at == EVENT["occurred_at"]
    assert event_id == str(EVENT["id"])


def test_cursor_is_parsed_and_forwarded_to_get_events():
    _as_user()
    with patch("routes.feed.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.feed.get_events", return_value=[]) as getter, \
         patch("routes.feed.count_events_since", return_value=0):
        client.get(
            "/feed",
            params={"cursor": "2026-03-04T10:00:00+00:00|1"},
            headers=HEADERS,
        )
    getter.assert_called_once_with(before_ts="2026-03-04T10:00:00+00:00", before_id=1, limit=50)


def test_malformed_cursor_is_treated_as_no_cursor():
    _as_user()
    with patch("routes.feed.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.feed.get_events", return_value=[]) as getter, \
         patch("routes.feed.count_events_since", return_value=0):
        resp = client.get("/feed", params={"cursor": "garbage"}, headers=HEADERS)
    assert resp.status_code == 200
    getter.assert_called_once_with(before_ts=None, before_id=None, limit=50)


def test_catch_up_advances_last_seen():
    _as_user()
    with patch("routes.feed.set_last_seen", return_value="2026-03-05T00:00:00+00:00") as setter:
        resp = client.post("/feed/seen", headers=HEADERS)
    assert resp.json()["last_seen_at"] == "2026-03-05T00:00:00+00:00"
    setter.assert_called_once_with("u1")


def test_catch_up_requires_a_device_key():
    assert client.post("/feed/seen").status_code == 401
