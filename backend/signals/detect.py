# backend/signals/detect.py
"""Where "meaningful change" is defined.

Four detectors, one rule each. The existence of a returned event IS the
judgment — there is no score and no ranking, so noise is never recorded
rather than being recorded and then hidden.

BIG_MOVE is measured against the symbol's own average daily range rather than
a flat percentage, because a 2% day means something different for a bank than
for a mid-cap coin.

Pure by contract: no I/O, no clock. See test_signal_modules_import_nothing_impure.
"""
from signals.types import Bar, DetectedEvent, SymbolStats

MOVE_RANGE_MULTIPLE = 2.0
VOLUME_MULTIPLE = 2.0
GAP_THRESHOLD = 0.015


def _severity(value: float, medium: float, high: float) -> int:
    if value >= high:
        return 3
    if value >= medium:
        return 2
    return 1


def _event(symbol, kind, latest, severity, payload) -> DetectedEvent:
    trading_day = latest.ts[:10]
    return DetectedEvent(
        symbol=symbol,
        kind=kind,
        occurred_at=latest.ts,
        severity=severity,
        payload=payload,
        dedupe_key=f"{symbol}|{kind}|{trading_day}",
    )


def _big_move(symbol, latest, prev, stats, min_move_pct):
    if not stats.avg_daily_range:
        return None
    # Subtract before dividing: `close / prev.close - 1` cancels two nearly
    # equal numbers and introduces float noise that pushes an exact multiple
    # (e.g. 2.0) a hair over the boundary.
    move = (latest.close - prev.close) / prev.close
    multiple = abs(move) / stats.avg_daily_range
    if multiple <= MOVE_RANGE_MULTIPLE:
        return None
    # A user floor is an ADDITIONAL constraint, never a replacement: the move
    # must clear both the volatility rule and the absolute percentage.
    if min_move_pct is not None and abs(move) * 100 < min_move_pct:
        return None
    return _event(symbol, "BIG_MOVE", latest, _severity(multiple, 3.0, 4.0), {
        "close": latest.close,
        "prev_close": prev.close,
        "move_pct": move * 100,
        "avg_daily_range": stats.avg_daily_range,
        "multiple": multiple,
    })


def _gap(symbol, latest, prev, stats):
    if latest.open is None:
        return None
    gap = latest.open / prev.close - 1
    if abs(gap) <= GAP_THRESHOLD:
        return None
    return _event(symbol, "GAP", latest, _severity(abs(gap), 0.03, 0.05), {
        "open": latest.open,
        "prev_close": prev.close,
        "gap_pct": gap * 100,
    })


def _volume_spike(symbol, latest, prev, stats):
    if not stats.avg_volume_20d or latest.volume is None:
        return None
    ratio = latest.volume / stats.avg_volume_20d
    if ratio <= VOLUME_MULTIPLE:
        return None
    return _event(symbol, "VOLUME_SPIKE", latest, _severity(ratio, 3.0, 5.0), {
        "volume": latest.volume,
        "avg_volume_20d": stats.avg_volume_20d,
        "ratio": ratio,
    })


def _range_break(symbol, latest, prev, stats):
    """A 52-week break outranks a 20-day one; only the wider scope is reported."""
    checks = [
        ("52w", 3, stats.high_52w, stats.low_52w),
        ("20d", 1, stats.high_20d, stats.low_20d),
    ]
    for scope, severity, high, low in checks:
        if high is not None and latest.close > high:
            return _event(symbol, "RANGE_BREAK", latest, severity, {
                "scope": scope, "direction": "high",
                "close": latest.close, "level": high,
            })
        if low is not None and latest.close < low:
            return _event(symbol, "RANGE_BREAK", latest, severity, {
                "scope": scope, "direction": "low",
                "close": latest.close, "level": low,
            })
    return None


def detect(
    symbol: str,
    latest: Bar,
    prev: Bar,
    stats: SymbolStats,
    min_move_pct: float | None = None,
) -> list[DetectedEvent]:
    """Return every event this bar triggers. Empty list means "nothing happened"."""
    if not prev.close or not latest.close:
        return []

    candidates = [
        _big_move(symbol, latest, prev, stats, min_move_pct),
        _gap(symbol, latest, prev, stats),
        _volume_spike(symbol, latest, prev, stats),
        _range_break(symbol, latest, prev, stats),
    ]
    return [event for event in candidates if event is not None]
