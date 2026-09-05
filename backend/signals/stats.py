# backend/signals/stats.py
"""Rolling statistics, computed once per refresh so detectors stay O(1).

Callers pass *completed* bars only — the pipeline excludes the in-progress
current day, because a half-formed bar would drag every average toward noon.
"""
import statistics

from signals.types import Bar, SymbolStats

RANGE_WINDOW = 20
VOLUME_WINDOW = 20
RETURN_WINDOW = 30


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def compute_stats(bars: list[Bar]) -> SymbolStats:
    """Derive rolling statistics from an ascending-by-time bar series."""
    if not bars:
        return SymbolStats()

    ranged = [b for b in bars if b.high is not None and b.low is not None and b.close]
    recent_ranged = ranged[-RANGE_WINDOW:]
    avg_daily_range = _mean([(b.high - b.low) / b.close for b in recent_ranged])

    volumes = [b.volume for b in bars[-VOLUME_WINDOW:] if b.volume is not None]
    avg_volume = _mean([float(v) for v in volumes])

    recent_for_returns = bars[-(RETURN_WINDOW + 1):]
    returns = []
    for prev, cur in zip(recent_for_returns, recent_for_returns[1:]):
        if prev.close:
            returns.append(cur.close / prev.close - 1)
    vol_30d = statistics.pstdev(returns) if len(returns) >= 2 else None

    highs = [b.high for b in ranged]
    lows = [b.low for b in ranged]
    recent_highs = [b.high for b in ranged[-RANGE_WINDOW:]]
    recent_lows = [b.low for b in ranged[-RANGE_WINDOW:]]

    return SymbolStats(
        avg_daily_range=avg_daily_range,
        avg_volume_20d=avg_volume,
        vol_30d=vol_30d,
        high_52w=max(highs) if highs else None,
        low_52w=min(lows) if lows else None,
        high_20d=max(recent_highs) if recent_highs else None,
        low_20d=min(recent_lows) if recent_lows else None,
    )
