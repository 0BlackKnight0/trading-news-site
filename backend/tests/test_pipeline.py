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


# --- run_news_refresh: symbol tagging ----------------------------------------

NEWS_ITEMS = [
    {
        "title": "Reliance Industries posts Q2 profit",
        "url": "https://example.com/reliance-q2",
        "source": "Test Wire",
        "category": "trading",
        "published_at": "2026-02-26T00:00:00+00:00",
        "summary": "Reliance Industries beat estimates this quarter.",
    },
    {
        "title": "China expands currency swap with Egypt",
        "url": "https://example.com/china-egypt",
        "source": "Test Wire",
        "category": "trading",
        "published_at": "2026-02-26T00:00:00+00:00",
        "summary": "Trade ties reach new heights amid shifting alliances.",
    },
]


def test_news_refresh_tags_article_mentioning_watchlist_company():
    with patch("aggregator_loop.fetch_all_news", return_value=NEWS_ITEMS), \
         patch("aggregator_loop.insert_news"), \
         patch("aggregator_loop.prune_news"), \
         patch("aggregator_loop.get_symbol_names",
               return_value={"RELIANCE.NS": "Reliance Industries Limited"}), \
         patch("aggregator_loop.tag_news_symbol") as tag:
        import aggregator_loop
        aggregator_loop.run_news_refresh()
    tag.assert_called_once_with("https://example.com/reliance-q2", "RELIANCE.NS")


def test_news_refresh_does_not_tag_article_mentioning_nothing():
    with patch("aggregator_loop.fetch_all_news", return_value=[NEWS_ITEMS[1]]), \
         patch("aggregator_loop.insert_news"), \
         patch("aggregator_loop.prune_news"), \
         patch("aggregator_loop.get_symbol_names",
               return_value={"RELIANCE.NS": "Reliance Industries Limited"}), \
         patch("aggregator_loop.tag_news_symbol") as tag:
        import aggregator_loop
        aggregator_loop.run_news_refresh()
    tag.assert_not_called()


def test_news_refresh_skips_tagging_when_no_symbol_names():
    with patch("aggregator_loop.fetch_all_news", return_value=NEWS_ITEMS), \
         patch("aggregator_loop.insert_news"), \
         patch("aggregator_loop.prune_news"), \
         patch("aggregator_loop.get_symbol_names", return_value={}), \
         patch("aggregator_loop.tag_news_symbol") as tag:
        import aggregator_loop
        aggregator_loop.run_news_refresh()
    tag.assert_not_called()


def test_news_refresh_still_prunes_news():
    with patch("aggregator_loop.fetch_all_news", return_value=NEWS_ITEMS), \
         patch("aggregator_loop.insert_news"), \
         patch("aggregator_loop.prune_news") as prune, \
         patch("aggregator_loop.get_symbol_names", return_value={}), \
         patch("aggregator_loop.tag_news_symbol"):
        import aggregator_loop
        aggregator_loop.run_news_refresh()
    prune.assert_called_once()


# --- Company names, needed to match news articles to symbols ---------------

def test_refresh_all_fetches_a_name_for_a_symbol_that_has_none():
    with patch("pipeline.get_symbol_names", return_value={}), \
         patch("pipeline.fetch_symbol_name", return_value="Reliance Industries Limited") as fetch_name, \
         patch("pipeline.upsert_symbol_name") as upsert_name, \
         patch("pipeline.fetch_bars", return_value=[]), \
         patch("pipeline.upsert_snapshots"), \
         patch("pipeline.get_snapshots", return_value=[]):
        import pipeline
        pipeline.refresh_all(["RELIANCE.NS"])
    fetch_name.assert_called_once_with("RELIANCE.NS")
    upsert_name.assert_called_once_with("RELIANCE.NS", "Reliance Industries Limited")


def test_refresh_all_skips_a_symbol_that_already_has_a_name():
    with patch("pipeline.get_symbol_names", return_value={"AAPL": "Apple Inc."}), \
         patch("pipeline.fetch_symbol_name") as fetch_name, \
         patch("pipeline.upsert_symbol_name") as upsert_name, \
         patch("pipeline.fetch_bars", return_value=[]), \
         patch("pipeline.upsert_snapshots"), \
         patch("pipeline.get_snapshots", return_value=[]):
        import pipeline
        pipeline.refresh_all(["AAPL"])
    fetch_name.assert_not_called()
    upsert_name.assert_not_called()


def test_refresh_all_does_not_store_a_name_when_yahoo_returns_none():
    with patch("pipeline.get_symbol_names", return_value={}), \
         patch("pipeline.fetch_symbol_name", return_value=None), \
         patch("pipeline.upsert_symbol_name") as upsert_name, \
         patch("pipeline.fetch_bars", return_value=[]), \
         patch("pipeline.upsert_snapshots"), \
         patch("pipeline.get_snapshots", return_value=[]):
        import pipeline
        pipeline.refresh_all(["BADSYM"])
    upsert_name.assert_not_called()
