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
