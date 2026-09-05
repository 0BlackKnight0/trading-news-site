# backend/tests/test_stats.py
from signals.stats import compute_stats
from signals.types import Bar


def _bars(closes, highs=None, lows=None, volumes=None):
    """Build a bar series; highs/lows default to a flat 2% band around close."""
    out = []
    for i, c in enumerate(closes):
        h = highs[i] if highs else c * 1.01
        l = lows[i] if lows else c * 0.99
        v = volumes[i] if volumes else 1000
        out.append(Bar(ts=f"2026-01-{i + 1:02d}T00:00:00+00:00",
                       open=c, high=h, low=l, close=c, volume=v))
    return out


def test_avg_daily_range_is_mean_of_high_low_over_close():
    stats = compute_stats(_bars([100.0] * 20))
    # each bar spans 101 to 99 on a 100 close -> 0.02
    assert round(stats.avg_daily_range, 6) == 0.02


def test_avg_volume_uses_last_twenty_bars_only():
    volumes = [10] * 30 + [100] * 20
    stats = compute_stats(_bars([100.0] * 50, volumes=volumes))
    assert stats.avg_volume_20d == 100


def test_52w_high_and_low_span_the_whole_series():
    stats = compute_stats(_bars([100.0, 250.0, 50.0, 100.0]))
    assert stats.high_52w == 250.0 * 1.01
    assert stats.low_52w == 50.0 * 0.99


def test_20d_range_uses_only_the_last_twenty_bars():
    closes = [500.0] + [100.0] * 20
    stats = compute_stats(_bars(closes))
    assert stats.high_20d == 100.0 * 1.01


def test_vol_30d_is_zero_for_a_flat_series():
    stats = compute_stats(_bars([100.0] * 31))
    assert stats.vol_30d == 0.0


def test_vol_30d_is_positive_when_returns_vary():
    stats = compute_stats(_bars([100.0, 110.0, 100.0, 115.0, 95.0]))
    assert stats.vol_30d > 0


def test_empty_series_yields_all_none():
    stats = compute_stats([])
    assert stats.avg_daily_range is None
    assert stats.high_52w is None
    assert stats.vol_30d is None


def test_single_bar_has_no_volatility_but_has_a_range():
    stats = compute_stats(_bars([100.0]))
    assert stats.vol_30d is None
    assert stats.high_52w == 101.0


def test_bars_missing_high_low_are_skipped_not_fatal():
    bars = [Bar(ts="2026-01-01T00:00:00+00:00", open=None, high=None,
                low=None, close=100.0, volume=None)]
    stats = compute_stats(bars)
    assert stats.avg_daily_range is None
    assert stats.avg_volume_20d is None
