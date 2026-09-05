# backend/tests/test_pipeline.py
from unittest.mock import patch

from signals.stats import compute_stats
from signals.types import Bar

BARS = [
    Bar(ts=f"2026-02-{d:02d}T00:00:00+00:00", open=100.0, high=101.0,
        low=99.0, close=100.0, volume=1000)
    for d in range(1, 26)
] + [
    Bar(ts="2026-02-26T00:00:00+00:00", open=100.0, high=110.0,
        low=100.0, close=109.0, volume=9000)
]


def _run(bars=BARS):
    """Run the pipeline with I/O replaced, returning (result, captured events)."""
    captured = []
    with patch("pipeline.fetch_bars", return_value=bars), \
         patch("pipeline.upsert_snapshots", return_value=len(bars)), \
         patch("pipeline.get_snapshots", return_value=bars), \
         patch("pipeline.upsert_symbol_stats"), \
         patch("pipeline.upsert_events", side_effect=lambda e: captured.extend(e) or len(e)):
        import pipeline
        result = pipeline.refresh_symbol("X")
    return result, captured


def test_refresh_symbol_detects_events_from_fetched_bars():
    result, captured = _run()
    assert result["symbol"] == "X"
    assert result["events"] > 0
    assert "BIG_MOVE" in {e.kind for e in captured}


def test_refresh_symbol_is_idempotent_on_dedupe_keys():
    """Re-running the pipeline must produce identical keys, so writes collapse."""
    _, first = _run()
    _, second = _run()
    assert [e.dedupe_key for e in first] == [e.dedupe_key for e in second]


def test_stats_exclude_the_in_progress_bar():
    """The latest bar is incomplete intraday; including it would flatten averages."""
    seen = {}

    def spy(bars):
        seen["n"] = len(bars)
        return compute_stats(bars)

    with patch("pipeline.fetch_bars", return_value=BARS), \
         patch("pipeline.upsert_snapshots"), \
         patch("pipeline.get_snapshots", return_value=BARS), \
         patch("pipeline.compute_stats", side_effect=spy), \
         patch("pipeline.upsert_symbol_stats"), \
         patch("pipeline.upsert_events", return_value=0):
        import pipeline
        pipeline.refresh_symbol("X")
    assert seen["n"] == len(BARS) - 1


def test_refresh_symbol_skips_symbols_with_too_little_history():
    result, captured = _run(bars=BARS[:1])
    assert result["events"] == 0
    assert captured == []


def test_refresh_all_continues_past_a_failing_symbol():
    def flaky(symbol, **kwargs):
        if symbol == "BAD":
            raise RuntimeError("yahoo down")
        return BARS

    with patch("pipeline.fetch_bars", side_effect=flaky), \
         patch("pipeline.upsert_snapshots"), \
         patch("pipeline.get_snapshots", return_value=BARS), \
         patch("pipeline.upsert_symbol_stats"), \
         patch("pipeline.upsert_events", return_value=1):
        import pipeline
        result = pipeline.refresh_all(["BAD", "GOOD"])
    assert result["symbols"] == 1
