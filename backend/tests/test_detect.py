# backend/tests/test_detect.py
import pathlib

from signals.detect import detect
from signals.types import Bar, SymbolStats

DAY = "2026-03-04T00:00:00+00:00"
PRIOR = "2026-03-03T00:00:00+00:00"


def _bar(close, open_=None, high=None, low=None, volume=1000, ts=DAY):
    return Bar(ts=ts, open=open_ if open_ is not None else close,
               high=high if high is not None else close,
               low=low if low is not None else close,
               close=close, volume=volume)


def _kinds(events):
    return {e.kind for e in events}


BASE = SymbolStats(avg_daily_range=0.02, avg_volume_20d=1000.0, vol_30d=0.015,
                   high_52w=120.0, low_52w=80.0, high_20d=110.0, low_20d=90.0)


# --- BIG_MOVE -------------------------------------------------------------

def test_big_move_fires_above_two_times_average_range():
    # +5% against a 2% average daily range = 2.5x
    events = detect("X", _bar(105.0), _bar(100.0, ts=PRIOR), BASE)
    assert "BIG_MOVE" in _kinds(events)


def test_big_move_silent_at_exactly_two_times():
    events = detect("X", _bar(104.0), _bar(100.0, ts=PRIOR), BASE)
    assert "BIG_MOVE" not in _kinds(events)


def test_big_move_severity_scales_with_the_multiple():
    high = [e for e in detect("X", _bar(109.0), _bar(100.0, ts=PRIOR), BASE)
            if e.kind == "BIG_MOVE"][0]
    assert high.severity == 3


def test_big_move_fires_on_downward_moves_too():
    events = detect("X", _bar(95.0), _bar(100.0, ts=PRIOR), BASE)
    assert "BIG_MOVE" in _kinds(events)


def test_big_move_respects_the_user_percentage_floor():
    # 5% move clears the volatility rule but not a 10% user floor
    events = detect("X", _bar(105.0), _bar(100.0, ts=PRIOR), BASE, min_move_pct=10.0)
    assert "BIG_MOVE" not in _kinds(events)


def test_big_move_needs_both_rules_not_either():
    # 3% move clears a 1% user floor but NOT the 2x volatility rule
    events = detect("X", _bar(103.0), _bar(100.0, ts=PRIOR), BASE, min_move_pct=1.0)
    assert "BIG_MOVE" not in _kinds(events)


def test_big_move_skipped_without_range_statistics():
    events = detect("X", _bar(150.0), _bar(100.0, ts=PRIOR), SymbolStats())
    assert "BIG_MOVE" not in _kinds(events)


def test_zero_previous_close_does_not_divide_by_zero():
    assert detect("X", _bar(105.0), _bar(0.0, ts=PRIOR), BASE) == []


# --- GAP ------------------------------------------------------------------

def test_gap_fires_above_one_and_a_half_percent():
    events = detect("X", _bar(100.0, open_=102.0), _bar(100.0, ts=PRIOR), BASE)
    assert "GAP" in _kinds(events)


def test_gap_silent_below_threshold():
    events = detect("X", _bar(100.0, open_=101.0), _bar(100.0, ts=PRIOR), BASE)
    assert "GAP" not in _kinds(events)


def test_gap_skipped_when_open_is_missing():
    bar = Bar(ts=DAY, open=None, high=100.0, low=100.0, close=100.0, volume=1000)
    events = detect("X", bar, _bar(100.0, ts=PRIOR), BASE)
    assert "GAP" not in _kinds(events)


# --- VOLUME_SPIKE ---------------------------------------------------------

def test_volume_spike_fires_above_two_times_average():
    events = detect("X", _bar(100.0, volume=2500), _bar(100.0, ts=PRIOR), BASE)
    assert "VOLUME_SPIKE" in _kinds(events)


def test_volume_spike_severity_three_at_five_times():
    spike = [e for e in detect("X", _bar(100.0, volume=6000), _bar(100.0, ts=PRIOR), BASE)
             if e.kind == "VOLUME_SPIKE"][0]
    assert spike.severity == 3


def test_volume_spike_skipped_when_volume_is_missing():
    events = detect("X", _bar(100.0, volume=None), _bar(100.0, ts=PRIOR), BASE)
    assert "VOLUME_SPIKE" not in _kinds(events)


# --- RANGE_BREAK ----------------------------------------------------------

def test_range_break_on_new_52_week_high():
    events = detect("X", _bar(125.0), _bar(119.0, ts=PRIOR), BASE)
    break_ = [e for e in events if e.kind == "RANGE_BREAK"][0]
    assert break_.severity == 3
    assert break_.payload["scope"] == "52w"


def test_range_break_on_new_52_week_low():
    events = detect("X", _bar(75.0), _bar(81.0, ts=PRIOR), BASE)
    break_ = [e for e in events if e.kind == "RANGE_BREAK"][0]
    assert break_.payload["direction"] == "low"


def test_range_break_falls_back_to_the_twenty_day_box():
    events = detect("X", _bar(112.0), _bar(109.0, ts=PRIOR), BASE)
    break_ = [e for e in events if e.kind == "RANGE_BREAK"][0]
    assert break_.payload["scope"] == "20d"
    assert break_.severity == 1


def test_range_break_reports_52w_not_20d_when_both_are_broken():
    events = detect("X", _bar(125.0), _bar(119.0, ts=PRIOR), BASE)
    breaks = [e for e in events if e.kind == "RANGE_BREAK"]
    assert len(breaks) == 1
    assert breaks[0].payload["scope"] == "52w"


def test_inside_the_range_produces_no_break():
    events = detect("X", _bar(100.0), _bar(100.0, ts=PRIOR), BASE)
    assert "RANGE_BREAK" not in _kinds(events)


# --- Event shape ----------------------------------------------------------

def test_dedupe_key_is_symbol_kind_and_trading_day():
    events = detect("RELIANCE", _bar(105.0), _bar(100.0, ts=PRIOR), BASE)
    move = [e for e in events if e.kind == "BIG_MOVE"][0]
    assert move.dedupe_key == "RELIANCE|BIG_MOVE|2026-03-04"


def test_occurred_at_is_the_bar_timestamp():
    events = detect("X", _bar(105.0), _bar(100.0, ts=PRIOR), BASE)
    assert events[0].occurred_at == DAY


def test_payload_carries_the_numbers_behind_the_claim():
    move = [e for e in detect("X", _bar(105.0), _bar(100.0, ts=PRIOR), BASE)
            if e.kind == "BIG_MOVE"][0]
    assert round(move.payload["move_pct"], 2) == 5.0
    assert move.payload["close"] == 105.0
    assert move.payload["prev_close"] == 100.0


def test_several_detectors_can_fire_on_one_bar():
    events = detect("X", _bar(125.0, open_=128.0, volume=9000),
                    _bar(119.0, ts=PRIOR), BASE)
    assert _kinds(events) == {"BIG_MOVE", "GAP", "VOLUME_SPIKE", "RANGE_BREAK"}


# --- Purity ---------------------------------------------------------------

def test_signal_modules_import_nothing_impure():
    """The definition of 'meaningful' must not depend on I/O or the clock."""
    banned = ("import requests", "import os", "from database", "import database",
              "datetime.now", "from supabase")
    for name in ("detect.py", "stats.py", "types.py"):
        source = (pathlib.Path(__file__).parent.parent / "signals" / name).read_text()
        for token in banned:
            assert token not in source, f"{name} must stay pure, found: {token}"
