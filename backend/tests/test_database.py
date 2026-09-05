# backend/tests/test_database.py
import os
os.environ["SUPABASE_URL"] = "http://fake.supabase.co"
# Supabase client validates key as JWT format — use a minimal valid-format token
os.environ["SUPABASE_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmYWtlIn0.fake_signature"

import database
from database import get_client

def test_get_client_returns_client():
    database._client = None  # reset singleton so env vars above take effect
    client = get_client()
    assert client is not None


from unittest.mock import MagicMock, patch

from signals.types import Bar, DetectedEvent, SymbolStats


def test_upsert_snapshots_sends_one_row_per_bar():
    bars = [Bar(ts="2026-01-01T00:00:00+00:00", open=1.0, high=2.0,
                low=0.5, close=1.5, volume=10)]
    table = MagicMock()
    with patch("database.get_client") as client:
        client.return_value.table.return_value = table
        assert database.upsert_snapshots("X", bars) == 1
    rows = table.upsert.call_args[0][0]
    assert rows[0]["symbol"] == "X"
    assert rows[0]["close"] == 1.5
    assert table.upsert.call_args[1]["on_conflict"] == "symbol,ts"


def test_upsert_snapshots_is_a_noop_for_no_bars():
    with patch("database.get_client") as client:
        assert database.upsert_snapshots("X", []) == 0
    client.assert_not_called()


def test_upsert_events_uses_dedupe_key_as_the_conflict_target():
    events = [DetectedEvent(symbol="X", kind="GAP", occurred_at="2026-01-01T00:00:00+00:00",
                            severity=2, payload={"gap_pct": 3.0}, dedupe_key="X|GAP|2026-01-01")]
    table = MagicMock()
    with patch("database.get_client") as client:
        client.return_value.table.return_value = table
        assert database.upsert_events(events) == 1
    assert table.upsert.call_args[1]["on_conflict"] == "dedupe_key"


def test_upsert_events_is_a_noop_for_no_events():
    with patch("database.get_client") as client:
        assert database.upsert_events([]) == 0
    client.assert_not_called()


def test_get_or_create_user_upserts_on_device_key():
    """Select-then-insert races two concurrent first-loads into a 23505 on
    users.device_key; an upsert on that column is race-proof instead."""
    users_table = MagicMock()
    users_table.upsert.return_value.execute.return_value = MagicMock(
        data=[{"id": "u1", "device_key": "abc"}]
    )
    user_state_table = MagicMock()

    def table(name):
        return {"users": users_table, "user_state": user_state_table}[name]

    with patch("database.get_client") as client:
        client.return_value.table.side_effect = table
        user = database.get_or_create_user("abc")

    assert user == {"id": "u1", "device_key": "abc"}
    assert users_table.upsert.call_args[0][0] == {"device_key": "abc"}
    assert users_table.upsert.call_args[1]["on_conflict"] == "device_key"


def test_get_or_create_user_upserts_user_state_even_for_an_existing_user():
    """If a prior call's users-write succeeded but its user_state-write
    failed, user_state must still get created on a later call — otherwise
    get_last_seen returns "now" forever and unread stays pinned at 0."""
    users_table = MagicMock()
    users_table.upsert.return_value.execute.return_value = MagicMock(
        data=[{"id": "u1", "device_key": "abc"}]
    )
    user_state_table = MagicMock()

    def table(name):
        return {"users": users_table, "user_state": user_state_table}[name]

    with patch("database.get_client") as client:
        client.return_value.table.side_effect = table
        database.get_or_create_user("abc")

    assert user_state_table.upsert.call_args[0][0]["user_id"] == "u1"
    assert user_state_table.upsert.call_args[1]["on_conflict"] == "user_id"


def test_get_snapshots_returns_ascending_bars():
    rows = [
        {"ts": "2026-01-02T00:00:00+00:00", "open": 2, "high": 3, "low": 1, "close": 2, "volume": 5},
        {"ts": "2026-01-01T00:00:00+00:00", "open": 1, "high": 2, "low": 0, "close": 1, "volume": 4},
    ]
    with patch("database.get_client") as client:
        chain = client.return_value.table.return_value.select.return_value.eq.return_value
        chain.order.return_value.limit.return_value.execute.return_value = MagicMock(data=rows)
        bars = database.get_snapshots("X")
    assert [b.ts for b in bars] == ["2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"]


def test_get_events_returns_empty_without_querying_for_no_symbols():
    with patch("database.get_client") as client:
        assert database.get_events([]) == []
    client.assert_not_called()


def test_get_events_filters_by_the_given_symbols():
    table = MagicMock()
    with patch("database.get_client") as client:
        client.return_value.table.return_value = table
        chain = table.select.return_value.in_.return_value.order.return_value.order.return_value.limit.return_value
        chain.execute.return_value = MagicMock(data=[])
        database.get_events(["RELIANCE", "TCS"])
    table.select.return_value.in_.assert_called_once_with("symbol", ["RELIANCE", "TCS"])


def test_count_events_since_returns_zero_without_querying_for_no_symbols():
    with patch("database.get_client") as client:
        assert database.count_events_since([], "2026-01-01T00:00:00+00:00") == 0
    client.assert_not_called()


def test_count_events_since_filters_by_symbols_and_compares_on_created_at():
    """occurred_at is the market session timestamp and is constant across an
    entire trading day, so the unread baseline must compare on created_at —
    when the row was actually written — not occurred_at."""
    table = MagicMock()
    with patch("database.get_client") as client:
        client.return_value.table.return_value = table
        chain = table.select.return_value.in_.return_value
        chain.gt.return_value.execute.return_value = MagicMock(count=3)
        count = database.count_events_since(["RELIANCE"], "2026-01-01T00:00:00+00:00")
    assert count == 3
    table.select.return_value.in_.assert_called_once_with("symbol", ["RELIANCE"])
    chain.gt.assert_called_once_with("created_at", "2026-01-01T00:00:00+00:00")


def test_get_news_orders_undated_articles_last():
    """Postgres defaults DESC to NULLS FIRST, which floats undated news
    above genuinely fresh articles and can fill the whole 20-row window."""
    with patch("database.get_client") as client:
        chain = client.return_value.table.return_value.select.return_value.eq.return_value
        chain.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        database.get_news("trading")
    assert chain.order.call_args[1]["nullsfirst"] is False


def test_prune_news_deletes_older_than_the_window():
    table = MagicMock()
    with patch("database.get_client") as client:
        client.return_value.table.return_value = table
        database.prune_news(days=30)
    table.delete.assert_called_once()
    assert table.delete.return_value.lt.call_args[0][0] == "published_at"
