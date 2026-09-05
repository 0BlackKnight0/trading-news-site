# backend/signals/types.py
"""Value types shared by the pure signal modules.

Nothing here touches the database, the network or the clock — these are the
inputs and outputs of `compute_stats` and `detect`, and that purity is what
makes the definition of "meaningful change" testable in isolation.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Bar:
    """One daily OHLCV bar. `ts` is an ISO 8601 UTC string."""
    ts: str
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: int | None


@dataclass(frozen=True)
class SymbolStats:
    """Rolling statistics for one symbol. None where there is too little history."""
    avg_daily_range: float | None = None
    avg_volume_20d: float | None = None
    vol_30d: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    high_20d: float | None = None
    low_20d: float | None = None


@dataclass(frozen=True)
class DetectedEvent:
    """One row destined for the `events` table."""
    symbol: str
    kind: str
    occurred_at: str
    severity: int
    payload: dict = field(default_factory=dict)
    dedupe_key: str = ""
