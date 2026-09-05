# The Line (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the watchlist into a changelog — an append-only event log written by pure threshold detectors, with an unread divider marking where the user last stopped reading.

**Architecture:** A refresh pipeline fetches daily bars from Yahoo, persists them to `price_snapshots`, recomputes rolling `symbol_stats`, then calls a pure `detect()` function that returns events. Events are written idempotently keyed on `symbol|kind|trading_day`. `GET /feed` returns them newest-first with an unread count against the caller's `last_seen_at`. Identity is a device key in `localStorage`, resolved server-side to a `users` row.

**Tech Stack:** Python 3.12 / FastAPI / supabase-py / Postgres (Supabase); Next.js 16 App Router / React 19 / TypeScript / Tailwind v4.

**Spec:** `docs/superpowers/specs/2026-09-05-smart-watchlist-design.md`

## Global Constraints

- Backend tests run from `backend/` with `./venv/bin/python -m pytest -q`. **All 40 existing tests must keep passing.**
- Frontend verification is `npx tsc --noEmit` then `npm run build`, both from `frontend/`.
- No new runtime dependencies. `backend/requirements.txt` stays at fastapi, uvicorn, python-dotenv, supabase, requests, feedparser. Statistics use the stdlib `statistics` module.
- `backend/schema.sql` must remain idempotent — every statement re-runnable against the live database.
- Detector modules under `backend/signals/` are **pure**: no imports of `database`, `requests`, `os`, or `datetime.now`. This is enforced by a test.
- Event kinds are exactly `BIG_MOVE`, `VOLUME_SPIKE`, `RANGE_BREAK`, `GAP`. `ALERT` is Phase 3.
- Timestamps are ISO 8601 UTC strings at every boundary.
- Accent colour for all "new"/unread affordances is `#ff5530`.

## Deviations from the spec (deliberate)

1. **`ALERT` deferred to Phase 3.** It requires a user-set price target whose configuration UI is Phase 3; a detector nothing can configure would be dead code.
2. **Events upsert `payload` and `severity` instead of `ON CONFLICT DO NOTHING`.** The current trading day's bar is incomplete intraday, so a move detected at 10:00 can fade by close. `occurred_at` records first detection and never moves; the numbers stay live.

## File Structure

| Path | Responsibility |
| --- | --- |
| `backend/schema.sql` | MODIFY — append new tables, idempotent |
| `backend/signals/__init__.py` | CREATE — empty package marker |
| `backend/signals/types.py` | CREATE — `Bar`, `SymbolStats`, `DetectedEvent` frozen dataclasses |
| `backend/signals/stats.py` | CREATE — pure `compute_stats(bars)` |
| `backend/signals/detect.py` | CREATE — pure `detect(...)`, the four detectors |
| `backend/aggregator/yahoo.py` | MODIFY — add `fetch_bars()` |
| `backend/database.py` | MODIFY — snapshot / stats / event / user accessors |
| `backend/pipeline.py` | CREATE — orchestration, the only module wiring the pure code to I/O |
| `backend/identity.py` | CREATE — device-key FastAPI dependency |
| `backend/routes/feed.py` | CREATE — `GET /feed`, `POST /feed/seen` |
| `backend/routes/watchlist.py` | MODIFY — user-scoped |
| `backend/routes/admin.py` | MODIFY — require `CRON_SECRET` |
| `backend/scripts/backfill.py` | CREATE — one-year history backfill |
| `frontend/types.ts` | MODIFY — `FeedEvent`, `FeedResponse` |
| `frontend/lib/deviceKey.ts` | CREATE — generate/persist the device key |
| `frontend/lib/api.ts` | MODIFY — send `X-Device-Key`, add feed calls |
| `frontend/components/EventRow.tsx` | CREATE — one changelog row |
| `frontend/components/Divider.tsx` | CREATE — the last-visit divider |
| `frontend/components/Feed.tsx` | CREATE — feed container, quiet state, catch-up |
| `frontend/app/page.tsx` | MODIFY — render `Feed` instead of `NewsFeed` |

---

## Task 1: Schema migration

**Files:**
- Modify: `backend/schema.sql`

**Interfaces:**
- Consumes: nothing
- Produces: tables `users`, `price_snapshots`, `symbol_stats`, `events`, `user_state`, `user_symbol_state`; `watchlist.user_id`

- [ ] **Step 1: Append the new tables to `backend/schema.sql`**

```sql
-- ===== The Line (Phase 1) =====

CREATE TABLE IF NOT EXISTS users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_key  TEXT UNIQUE NOT NULL,
  sync_code   TEXT UNIQUE,
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS price_snapshots (
  id      BIGSERIAL PRIMARY KEY,
  symbol  TEXT NOT NULL,
  ts      TIMESTAMPTZ NOT NULL,
  open    NUMERIC,
  high    NUMERIC,
  low     NUMERIC,
  close   NUMERIC,
  volume  BIGINT,
  source  TEXT NOT NULL DEFAULT 'yahoo',
  UNIQUE (symbol, ts)
);
CREATE INDEX IF NOT EXISTS price_snapshots_symbol_ts_idx
  ON price_snapshots (symbol, ts DESC);

CREATE TABLE IF NOT EXISTS symbol_stats (
  symbol           TEXT PRIMARY KEY,
  avg_daily_range  NUMERIC,
  avg_volume_20d   BIGINT,
  vol_30d          NUMERIC,
  high_52w         NUMERIC,
  low_52w          NUMERIC,
  high_20d         NUMERIC,
  low_20d          NUMERIC,
  computed_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (
  id           BIGSERIAL PRIMARY KEY,
  symbol       TEXT NOT NULL,
  kind         TEXT NOT NULL,
  occurred_at  TIMESTAMPTZ NOT NULL,
  severity     SMALLINT NOT NULL DEFAULT 1,
  payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
  dedupe_key   TEXT UNIQUE NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS events_occurred_at_idx ON events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS events_symbol_occurred_idx ON events (symbol, occurred_at DESC);

CREATE TABLE IF NOT EXISTS user_state (
  user_id       UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_symbol_state (
  user_id       UUID REFERENCES users(id) ON DELETE CASCADE,
  symbol        TEXT NOT NULL,
  muted         BOOLEAN NOT NULL DEFAULT false,
  min_move_pct  NUMERIC,
  pinned        BOOLEAN NOT NULL DEFAULT false,
  PRIMARY KEY (user_id, symbol)
);

-- watchlist becomes per-user. The old global UNIQUE(symbol) is replaced.
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE watchlist DROP CONSTRAINT IF EXISTS watchlist_symbol_key;
CREATE UNIQUE INDEX IF NOT EXISTS watchlist_user_symbol_idx ON watchlist (user_id, symbol);

-- news_cache: replace the Python-side title dedupe with a real constraint.
DELETE FROM news_cache a USING news_cache b WHERE a.id > b.id AND a.url = b.url;
CREATE UNIQUE INDEX IF NOT EXISTS news_cache_url_idx ON news_cache (url);
```

- [ ] **Step 2: Run the migration in the Supabase SQL editor**

Paste the whole of `backend/schema.sql` into the Supabase SQL editor and run it.
Expected: `Success. No rows returned`.

- [ ] **Step 3: Verify the tables exist**

Run in the SQL editor:

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' ORDER BY table_name;
```

Expected to include: `events`, `market_cache`, `news_cache`, `price_snapshots`, `refresh_meta`, `symbol_stats`, `telegram_users`, `user_state`, `user_symbol_state`, `users`, `watchlist`.

- [ ] **Step 4: Commit**

```bash
git add backend/schema.sql
git commit -m "feat: add schema for snapshots, stats, events and per-user state"
```

---

## Task 2: Signal types and rolling statistics

**Files:**
- Create: `backend/signals/__init__.py`
- Create: `backend/signals/types.py`
- Create: `backend/signals/stats.py`
- Test: `backend/tests/test_stats.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `Bar(ts: str, open: float|None, high: float|None, low: float|None, close: float, volume: int|None)`
  - `SymbolStats(avg_daily_range, avg_volume_20d, vol_30d, high_52w, low_52w, high_20d, low_20d)` — all `float|None`
  - `DetectedEvent(symbol: str, kind: str, occurred_at: str, severity: int, payload: dict, dedupe_key: str)`
  - `compute_stats(bars: list[Bar]) -> SymbolStats`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_stats.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_stats.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'signals'`

- [ ] **Step 3: Create the package marker**

Create `backend/signals/__init__.py` as an empty file.

- [ ] **Step 4: Write the types**

Create `backend/signals/types.py`:

```python
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
```

- [ ] **Step 5: Write the statistics**

Create `backend/signals/stats.py`:

```python
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

    returns = []
    for prev, cur in zip(bars[-(RETURN_WINDOW + 1):], bars[-RETURN_WINDOW:]):
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
```

- [ ] **Step 6: Run to verify it passes**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_stats.py -q`
Expected: `9 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/signals/__init__.py backend/signals/types.py backend/signals/stats.py backend/tests/test_stats.py
git commit -m "feat: pure rolling statistics for signal detection"
```

---

## Task 3: The detectors

**Files:**
- Create: `backend/signals/detect.py`
- Test: `backend/tests/test_detect.py`

**Interfaces:**
- Consumes: `Bar`, `SymbolStats`, `DetectedEvent` from `signals.types`
- Produces: `detect(symbol: str, latest: Bar, prev: Bar, stats: SymbolStats, min_move_pct: float | None = None) -> list[DetectedEvent]`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_detect.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_detect.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'signals.detect'`

- [ ] **Step 3: Write the detectors**

Create `backend/signals/detect.py`:

```python
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
    move = latest.close / prev.close - 1
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_detect.py -q`
Expected: `23 passed`

- [ ] **Step 5: Run the whole suite to confirm nothing regressed**

Run: `cd backend && ./venv/bin/python -m pytest -q`
Expected: `72 passed` (40 existing + 9 stats + 23 detect)

- [ ] **Step 6: Commit**

```bash
git add backend/signals/detect.py backend/tests/test_detect.py
git commit -m "feat: threshold detectors defining meaningful change"
```

---

## Task 4: Fetch daily bars from Yahoo

**Files:**
- Modify: `backend/aggregator/yahoo.py`
- Test: `backend/tests/test_yahoo.py`

**Interfaces:**
- Consumes: `fetch_chart(symbol, interval, range_)` — already exists in this file
- Produces: `bars_from_chart(chart: dict) -> list[Bar]` and `fetch_bars(symbol: str, range_: str = "3mo") -> list[Bar]`

- [ ] **Step 1: Append the failing tests to `backend/tests/test_yahoo.py`**

```python
# --- Bar extraction -------------------------------------------------------

from aggregator.yahoo import bars_from_chart


def _chart_with_series(timestamps, opens, highs, lows, closes, volumes):
    return {
        "meta": {"regularMarketPrice": closes[-1], "currency": "INR"},
        "timestamp": timestamps,
        "indicators": {"quote": [{
            "open": opens, "high": highs, "low": lows,
            "close": closes, "volume": volumes,
        }]},
    }


def test_bars_from_chart_builds_ascending_bars():
    chart = _chart_with_series(
        [1767225600, 1767312000], [100.0, 102.0], [103.0, 105.0],
        [99.0, 101.0], [102.0, 104.0], [1000, 2000],
    )
    bars = bars_from_chart(chart)
    assert len(bars) == 2
    assert bars[0].close == 102.0
    assert bars[1].volume == 2000
    assert bars[0].ts < bars[1].ts


def test_bars_from_chart_drops_rows_with_no_close():
    """Yahoo pads the series with nulls on non-trading days."""
    chart = _chart_with_series(
        [1767225600, 1767312000], [100.0, None], [103.0, None],
        [99.0, None], [102.0, None], [1000, None],
    )
    bars = bars_from_chart(chart)
    assert len(bars) == 1


def test_bars_from_chart_returns_empty_for_an_empty_chart():
    assert bars_from_chart({}) == []


def test_bars_timestamps_are_iso_utc():
    chart = _chart_with_series([1767225600], [100.0], [103.0], [99.0], [102.0], [1000])
    assert bars_from_chart(chart)[0].ts.endswith("+00:00")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_yahoo.py -q`
Expected: FAIL, `ImportError: cannot import name 'bars_from_chart'`

- [ ] **Step 3: Add the functions to `backend/aggregator/yahoo.py`**

Add this import at the top of the file, after `import requests`:

```python
from datetime import datetime, timezone

from signals.types import Bar
```

Then append to the end of the file:

```python
def bars_from_chart(chart: dict) -> list[Bar]:
    """Extract ascending daily bars from a chart result.

    Yahoo pads the series with nulls on non-trading days; those rows are
    dropped rather than carried forward, so averages are not diluted.
    """
    timestamps = chart.get("timestamp") or []
    quotes = (chart.get("indicators") or {}).get("quote") or [{}]
    ohlcv = quotes[0] if quotes else {}

    closes = ohlcv.get("close") or []
    opens = ohlcv.get("open") or []
    highs = ohlcv.get("high") or []
    lows = ohlcv.get("low") or []
    volumes = ohlcv.get("volume") or []

    def at(series, i):
        return series[i] if i < len(series) else None

    bars = []
    for i, epoch in enumerate(timestamps):
        close = at(closes, i)
        if close is None:
            continue
        ts = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
        volume = at(volumes, i)
        bars.append(Bar(
            ts=ts,
            open=at(opens, i),
            high=at(highs, i),
            low=at(lows, i),
            close=float(close),
            volume=int(volume) if volume is not None else None,
        ))
    return bars


def fetch_bars(symbol: str, range_: str = "3mo") -> list[Bar]:
    """Daily bars for a symbol. Returns [] on any failure."""
    return bars_from_chart(fetch_chart(symbol, interval="1d", range_=range_))
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_yahoo.py -q`
Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/aggregator/yahoo.py backend/tests/test_yahoo.py
git commit -m "feat: extract daily bars from the Yahoo chart response"
```

---

## Task 5: Database accessors for snapshots, stats and events

**Files:**
- Modify: `backend/database.py`
- Test: `backend/tests/test_database.py`

**Interfaces:**
- Consumes: `get_client()` — already exists
- Produces:
  - `upsert_snapshots(symbol: str, bars: list[Bar]) -> int`
  - `get_snapshots(symbol: str, limit: int = 260) -> list[Bar]`
  - `upsert_symbol_stats(symbol: str, stats: SymbolStats) -> None`
  - `upsert_events(events: list[DetectedEvent]) -> int`
  - `get_events(before: str | None, limit: int) -> list[dict]`
  - `count_events_since(ts: str) -> int`
  - `get_or_create_user(device_key: str) -> dict`
  - `get_last_seen(user_id: str) -> str`
  - `set_last_seen(user_id: str) -> str`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_database.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_database.py -q`
Expected: FAIL, `AttributeError: module 'database' has no attribute 'upsert_snapshots'`

- [ ] **Step 3: Append the accessors to `backend/database.py`**

Add this import near the top, after the existing `from supabase import ...` line:

```python
from signals.types import Bar, DetectedEvent, SymbolStats
```

Then append to the end of the file:

```python
# --- The Line: snapshots, stats, events, users ---------------------------

def upsert_snapshots(symbol: str, bars: list[Bar]) -> int:
    """Persist daily bars. Idempotent on (symbol, ts)."""
    if not bars:
        return 0
    rows = [{
        "symbol": symbol, "ts": b.ts, "open": b.open, "high": b.high,
        "low": b.low, "close": b.close, "volume": b.volume, "source": "yahoo",
    } for b in bars]
    get_client().table("price_snapshots").upsert(rows, on_conflict="symbol,ts").execute()
    return len(rows)


def get_snapshots(symbol: str, limit: int = 260) -> list[Bar]:
    """The most recent `limit` bars for a symbol, returned oldest-first."""
    res = (get_client().table("price_snapshots")
           .select("ts, open, high, low, close, volume")
           .eq("symbol", symbol)
           .order("ts", desc=True)
           .limit(limit)
           .execute())
    bars = [Bar(ts=r["ts"], open=r["open"], high=r["high"], low=r["low"],
                close=float(r["close"]), volume=r["volume"])
            for r in reversed(res.data or []) if r.get("close") is not None]
    return bars


def upsert_symbol_stats(symbol: str, stats: SymbolStats) -> None:
    get_client().table("symbol_stats").upsert({
        "symbol": symbol,
        "avg_daily_range": stats.avg_daily_range,
        "avg_volume_20d": int(stats.avg_volume_20d) if stats.avg_volume_20d else None,
        "vol_30d": stats.vol_30d,
        "high_52w": stats.high_52w,
        "low_52w": stats.low_52w,
        "high_20d": stats.high_20d,
        "low_20d": stats.low_20d,
        "computed_at": _now_iso(),
    }, on_conflict="symbol").execute()


def upsert_events(events: list[DetectedEvent]) -> int:
    """Write events idempotently.

    Payload and severity are refreshed rather than ignored: the current day's
    bar is incomplete intraday, so a move detected at 10:00 can fade by close.
    `occurred_at` pins first detection and never moves.
    """
    if not events:
        return 0
    rows = [{
        "symbol": e.symbol, "kind": e.kind, "occurred_at": e.occurred_at,
        "severity": e.severity, "payload": e.payload, "dedupe_key": e.dedupe_key,
    } for e in events]
    get_client().table("events").upsert(rows, on_conflict="dedupe_key").execute()
    return len(rows)


def get_events(before: str | None = None, limit: int = 50) -> list[dict]:
    """Events newest-first. `before` is a cursor on occurred_at."""
    query = (get_client().table("events")
             .select("*")
             .order("occurred_at", desc=True)
             .limit(limit))
    if before:
        query = query.lt("occurred_at", before)
    return query.execute().data or []


def count_events_since(ts: str) -> int:
    res = (get_client().table("events")
           .select("id", count="exact")
           .gt("occurred_at", ts)
           .execute())
    return res.count or 0


def get_or_create_user(device_key: str) -> dict:
    existing = (get_client().table("users")
                .select("*").eq("device_key", device_key).limit(1).execute())
    if existing.data:
        return existing.data[0]
    created = get_client().table("users").insert({"device_key": device_key}).execute()
    user = created.data[0]
    get_client().table("user_state").upsert(
        {"user_id": user["id"], "last_seen_at": _now_iso()}, on_conflict="user_id"
    ).execute()
    return user


def get_last_seen(user_id: str) -> str:
    res = (get_client().table("user_state")
           .select("last_seen_at").eq("user_id", user_id).limit(1).execute())
    if res.data and res.data[0].get("last_seen_at"):
        return res.data[0]["last_seen_at"]
    return _now_iso()


def set_last_seen(user_id: str) -> str:
    stamp = _now_iso()
    get_client().table("user_state").upsert(
        {"user_id": user_id, "last_seen_at": stamp}, on_conflict="user_id"
    ).execute()
    return stamp
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_database.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/database.py backend/tests/test_database.py
git commit -m "feat: database accessors for snapshots, stats, events and users"
```

---

## Task 6: The refresh pipeline

**Files:**
- Create: `backend/pipeline.py`
- Test: `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `fetch_bars`, `compute_stats`, `detect`, and the Task 5 accessors
- Produces: `refresh_symbol(symbol: str, min_move_pct: float | None = None) -> dict` returning `{"symbol", "bars", "events"}`, and `refresh_all(symbols: list[str]) -> dict` returning `{"symbols", "events"}`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline.py`:

```python
# backend/tests/test_pipeline.py
from unittest.mock import patch

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
    with patch("pipeline.fetch_bars", return_value=BARS), \
         patch("pipeline.upsert_snapshots"), \
         patch("pipeline.get_snapshots", return_value=BARS), \
         patch("pipeline.compute_stats", side_effect=lambda b: seen.update(n=len(b)) or __import__("signals.stats", fromlist=["compute_stats"]).compute_stats(b)), \
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_pipeline.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'pipeline'`

- [ ] **Step 3: Write the pipeline**

Create `backend/pipeline.py`:

```python
# backend/pipeline.py
"""Wires the pure signal code to I/O.

This is the only module that both talks to the database and calls the
detectors, which is what lets everything under `signals/` stay pure.

Every write is idempotent, so a duplicated cron invocation or an overlapping
on-read refresh is harmless and the work is resumable after a timeout.
"""
import logging

from aggregator.yahoo import fetch_bars
from database import (
    get_snapshots,
    upsert_events,
    upsert_snapshots,
    upsert_symbol_stats,
)
from signals.detect import detect
from signals.stats import compute_stats

logger = logging.getLogger(__name__)

FETCH_RANGE = "3mo"
HISTORY_LIMIT = 260


def refresh_symbol(symbol: str, min_move_pct: float | None = None) -> dict:
    """Fetch, persist, recompute and detect for one symbol."""
    bars = fetch_bars(symbol, range_=FETCH_RANGE)
    if len(bars) < 2:
        logger.info(f"{symbol}: too few bars ({len(bars)}), skipping")
        return {"symbol": symbol, "bars": len(bars), "events": 0}

    upsert_snapshots(symbol, bars)
    history = get_snapshots(symbol, limit=HISTORY_LIMIT)
    if len(history) < 2:
        return {"symbol": symbol, "bars": len(bars), "events": 0}

    # The last bar is the in-progress trading day. Statistics are computed
    # from completed bars only; the detectors compare it against them.
    stats = compute_stats(history[:-1])
    upsert_symbol_stats(symbol, stats)

    events = detect(symbol, history[-1], history[-2], stats, min_move_pct)
    upsert_events(events)

    return {"symbol": symbol, "bars": len(bars), "events": len(events)}


def refresh_all(symbols: list[str]) -> dict:
    """Refresh many symbols. One failure never stops the rest."""
    ok, total_events = 0, 0
    for symbol in symbols:
        try:
            result = refresh_symbol(symbol)
            ok += 1
            total_events += result["events"]
        except Exception as e:
            logger.error(f"refresh failed for {symbol}: {e}")
    return {"symbols": ok, "events": total_events}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_pipeline.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: refresh pipeline wiring detectors to persistence"
```

---

## Task 7: Device-key identity

**Files:**
- Create: `backend/identity.py`
- Test: `backend/tests/test_identity.py`

**Interfaces:**
- Consumes: `get_or_create_user` from Task 5
- Produces: `current_user(x_device_key: str | None) -> dict` — a FastAPI dependency returning a `users` row

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_identity.py`:

```python
# backend/tests/test_identity.py
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from identity import MIN_KEY_LENGTH, current_user

VALID_KEY = "d" * MIN_KEY_LENGTH


def test_missing_device_key_is_rejected():
    with pytest.raises(HTTPException) as err:
        current_user(None)
    assert err.value.status_code == 401


def test_short_device_key_is_rejected():
    """A guessable key would let anyone assume another user's identity."""
    with pytest.raises(HTTPException) as err:
        current_user("abc")
    assert err.value.status_code == 401


def test_valid_device_key_resolves_to_a_user():
    with patch("identity.get_or_create_user", return_value={"id": "u1"}) as lookup:
        user = current_user(VALID_KEY)
    assert user["id"] == "u1"
    lookup.assert_called_once_with(VALID_KEY)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_identity.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'identity'`

- [ ] **Step 3: Write the dependency**

Create `backend/identity.py`:

```python
# backend/identity.py
"""Device-key identity.

A key generated in the browser and kept in localStorage, exchanged for a
`users` row on first contact. This is deliberately not authentication —
anyone holding the key is that user — but it replaces the current build's
single global watchlist that any visitor can edit.

Keys must be long enough not to be guessable; a UUID v4 satisfies this.
"""
from fastapi import Header, HTTPException

from database import get_or_create_user

MIN_KEY_LENGTH = 32


def current_user(x_device_key: str | None = Header(default=None)) -> dict:
    if not x_device_key or len(x_device_key.strip()) < MIN_KEY_LENGTH:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Device-Key")
    return get_or_create_user(x_device_key.strip())
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_identity.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/identity.py backend/tests/test_identity.py
git commit -m "feat: device-key identity dependency"
```

---

## Task 8: The feed API

**Files:**
- Create: `backend/routes/feed.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_feed_routes.py`

**Interfaces:**
- Consumes: `current_user`, `get_events`, `count_events_since`, `get_last_seen`, `set_last_seen`
- Produces: `GET /feed` returning `{"events", "unread_count", "last_seen_at", "next_cursor"}`; `POST /feed/seen` returning `{"last_seen_at"}`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_feed_routes.py`:

```python
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
    assert body["next_cursor"] == "2026-03-04T10:00:00+00:00"


def test_catch_up_advances_last_seen():
    _as_user()
    with patch("routes.feed.set_last_seen", return_value="2026-03-05T00:00:00+00:00") as setter:
        resp = client.post("/feed/seen", headers=HEADERS)
    assert resp.json()["last_seen_at"] == "2026-03-05T00:00:00+00:00"
    setter.assert_called_once_with("u1")


def test_catch_up_requires_a_device_key():
    assert client.post("/feed/seen").status_code == 401
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_feed_routes.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'routes.feed'`

- [ ] **Step 3: Write the route**

Create `backend/routes/feed.py`:

```python
# backend/routes/feed.py
"""The changelog.

`GET /feed` is the whole product: events newest-first, plus the count of
those the caller has not seen. The divider the UI draws sits at
`last_seen_at`.
"""
from fastapi import APIRouter, Depends, Query

from database import count_events_since, get_events, get_last_seen, set_last_seen
from identity import current_user

router = APIRouter()

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@router.get("/feed")
def feed(
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    cursor: str | None = Query(default=None),
    since: str | None = Query(default=None),
    user: dict = Depends(current_user),
):
    # `since` lets the client re-anchor the divider ("show me this week");
    # by default the baseline is where the user actually stopped reading.
    baseline = since or get_last_seen(user["id"])
    events = get_events(before=cursor, limit=limit)
    return {
        "events": events,
        "unread_count": count_events_since(baseline),
        "last_seen_at": baseline,
        "next_cursor": events[-1]["occurred_at"] if len(events) == limit else None,
    }


@router.post("/feed/seen")
def seen(user: dict = Depends(current_user)):
    """Catch up — move the divider to now."""
    return {"last_seen_at": set_last_seen(user["id"])}
```

- [ ] **Step 4: Register the router in `backend/main.py`**

Add to the import block:

```python
from routes.feed import router as feed_router
```

Add alongside the other `include_router` calls:

```python
app.include_router(feed_router)
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_feed_routes.py -q`
Expected: `8 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/routes/feed.py backend/main.py backend/tests/test_feed_routes.py
git commit -m "feat: GET /feed and POST /feed/seen"
```

---

## Task 9: User-scoped watchlist and a closed admin endpoint

**Files:**
- Modify: `backend/routes/watchlist.py`
- Modify: `backend/routes/admin.py`
- Modify: `backend/database.py`
- Test: `backend/tests/test_routes.py`

**Interfaces:**
- Consumes: `current_user`
- Produces: `get_watchlist(user_id)`, `add_to_watchlist(user_id, symbol, type_)`, `remove_from_watchlist(user_id, symbol)`, `get_all_watched_symbols() -> list[str]`

- [ ] **Step 1: Replace the watchlist tests in `backend/tests/test_routes.py`**

Delete `test_watchlist_get`, `test_watchlist_post` and `test_watchlist_delete`, and add:

```python
from identity import MIN_KEY_LENGTH, current_user

WL_HEADERS = {"X-Device-Key": "w" * MIN_KEY_LENGTH}


def _as_watchlist_user(user_id="u1"):
    app.dependency_overrides[current_user] = lambda: {"id": user_id}


def teardown_function():
    app.dependency_overrides.clear()


def test_watchlist_requires_a_device_key():
    assert client.get("/watchlist").status_code == 401


def test_watchlist_get_is_scoped_to_the_caller():
    _as_watchlist_user("u42")
    with patch("routes.watchlist.get_watchlist", return_value=[]) as getter:
        resp = client.get("/watchlist", headers=WL_HEADERS)
    assert resp.status_code == 200
    getter.assert_called_once_with("u42")


def test_watchlist_post_records_the_owner():
    _as_watchlist_user("u42")
    with patch("routes.watchlist.add_to_watchlist") as adder:
        resp = client.post("/watchlist", json={"symbol": "RELIANCE", "type": "stock"},
                           headers=WL_HEADERS)
    assert resp.json()["symbol"] == "RELIANCE"
    adder.assert_called_once_with("u42", "RELIANCE", "stock")


def test_watchlist_delete_is_scoped_to_the_caller():
    _as_watchlist_user("u42")
    with patch("routes.watchlist.remove_from_watchlist") as remover:
        resp = client.delete("/watchlist/RELIANCE", headers=WL_HEADERS)
    assert resp.json()["symbol"] == "RELIANCE"
    remover.assert_called_once_with("u42", "RELIANCE")


def test_admin_refresh_rejects_a_missing_secret(monkeypatch):
    """Currently open to the world — anyone can trigger a full refresh."""
    monkeypatch.setenv("CRON_SECRET", "s3cret-value-1234")
    assert client.post("/admin/refresh").status_code == 401


def test_admin_refresh_accepts_the_cron_secret(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret-value-1234")
    with patch("routes.admin.run_market_refresh"), patch("routes.admin.run_news_refresh"), \
         patch("routes.admin.get_market", return_value=[]), \
         patch("routes.admin.get_news", return_value=[]):
        resp = client.post("/admin/refresh",
                           headers={"Authorization": "Bearer s3cret-value-1234"})
    assert resp.status_code == 200
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_routes.py -q`
Expected: FAIL — watchlist calls do not take a user id, and `/admin/refresh` returns 200 without a secret.

- [ ] **Step 3: Replace the watchlist accessors in `backend/database.py`**

Replace the existing `get_watchlist`, `add_to_watchlist` and `remove_from_watchlist` with:

```python
def get_watchlist(user_id: str) -> list[dict]:
    return (get_client().table("watchlist")
            .select("*").eq("user_id", user_id).execute().data)


def add_to_watchlist(user_id: str, symbol: str, type_: str):
    get_client().table("watchlist").upsert(
        {"user_id": user_id, "symbol": symbol.upper(), "type": type_},
        on_conflict="user_id,symbol",
    ).execute()


def remove_from_watchlist(user_id: str, symbol: str):
    (get_client().table("watchlist")
     .delete().eq("user_id", user_id).eq("symbol", symbol.upper()).execute())


def get_all_watched_symbols() -> list[str]:
    """Every symbol on any watchlist — the refresh pipeline's work queue."""
    rows = get_client().table("watchlist").select("symbol").execute().data or []
    return sorted({r["symbol"] for r in rows})
```

- [ ] **Step 4: Rewrite `backend/routes/watchlist.py`**

```python
# backend/routes/watchlist.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from database import add_to_watchlist, get_watchlist, remove_from_watchlist
from identity import current_user

router = APIRouter()


class WatchlistItem(BaseModel):
    symbol: str
    type: str


@router.get("/watchlist")
def list_watchlist(user: dict = Depends(current_user)):
    return get_watchlist(user["id"])


@router.post("/watchlist")
def add_watchlist(item: WatchlistItem, user: dict = Depends(current_user)):
    add_to_watchlist(user["id"], item.symbol.upper(), item.type)
    return {"status": "added", "symbol": item.symbol.upper()}


@router.delete("/watchlist/{symbol}")
def delete_watchlist(symbol: str, user: dict = Depends(current_user)):
    remove_from_watchlist(user["id"], symbol.upper())
    return {"status": "removed", "symbol": symbol.upper()}
```

- [ ] **Step 5: Close `/admin/refresh` in `backend/routes/admin.py`**

Change the imports at the top to:

```python
from fastapi import APIRouter, Depends, Header, HTTPException
```

Add above the route, and add `_ = Depends(require_cron_secret)` as a parameter:

```python
import os


def require_cron_secret(authorization: str | None = Header(default=None)):
    """Same gate as /cron/daily — this endpoint triggers real outbound work."""
    secret = os.environ.get("CRON_SECRET", "")
    if not secret or authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")
```

Change the route signature from `def force_refresh():` to:

```python
@router.post("/refresh")
def force_refresh(_: None = Depends(require_cron_secret)):
```

- [ ] **Step 6: Run the full suite**

Run: `cd backend && ./venv/bin/python -m pytest -q`
Expected: all tests pass, including the pre-existing cron and telegram cases.

- [ ] **Step 7: Commit**

```bash
git add backend/routes/watchlist.py backend/routes/admin.py backend/database.py backend/tests/test_routes.py
git commit -m "feat: scope the watchlist to a user and close /admin/refresh"
```

---

## Task 10: Backfill script

**Files:**
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/backfill.py`

**Interfaces:**
- Consumes: `fetch_bars`, `upsert_snapshots`, `get_all_watched_symbols`
- Produces: a CLI — `python -m scripts.backfill [SYMBOL ...]`

- [ ] **Step 1: Create the package marker**

Create `backend/scripts/__init__.py` as an empty file.

- [ ] **Step 2: Write the script**

Create `backend/scripts/backfill.py`:

```python
# backend/scripts/backfill.py
"""Seed one year of daily bars.

Without history there are no statistics, therefore no detectors, therefore an
empty feed — and nothing for the Rewind scrubber to move through. Run this
once per symbol; it is idempotent on (symbol, ts) so re-running is free.

Usage:
    ./venv/bin/python -m scripts.backfill              # every watched symbol
    ./venv/bin/python -m scripts.backfill RELIANCE.NS  # specific symbols
"""
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

from aggregator.yahoo import fetch_bars           # noqa: E402
from database import get_all_watched_symbols, upsert_snapshots  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill")

BACKFILL_RANGE = "1y"


def backfill(symbols: list[str]) -> int:
    total = 0
    for symbol in symbols:
        try:
            bars = fetch_bars(symbol, range_=BACKFILL_RANGE)
            written = upsert_snapshots(symbol, bars)
            total += written
            logger.info(f"{symbol}: {written} bars")
        except Exception as e:
            logger.error(f"{symbol}: FAILED — {e}")
    return total


def main():
    symbols = sys.argv[1:] or get_all_watched_symbols()
    if not symbols:
        logger.info("No symbols to backfill.")
        return
    logger.info(f"Backfilling {len(symbols)} symbol(s)...")
    logger.info(f"Done. {backfill(symbols)} bars written.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run it against one symbol**

Run: `cd backend && ./venv/bin/python -m scripts.backfill RELIANCE.NS`
Expected: `RELIANCE.NS: 240 bars` (roughly — one year of trading days), then `Done.`

- [ ] **Step 4: Verify the rows landed**

Run in the Supabase SQL editor:

```sql
SELECT count(*), min(ts), max(ts) FROM price_snapshots WHERE symbol = 'RELIANCE.NS';
```

Expected: a count near 240 spanning roughly twelve months.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/__init__.py backend/scripts/backfill.py
git commit -m "feat: one-year history backfill script"
```

---

## Task 11: Frontend types, device key and API client

**Files:**
- Modify: `frontend/types.ts`
- Create: `frontend/lib/deviceKey.ts`
- Modify: `frontend/lib/api.ts`

**Interfaces:**
- Produces: `FeedEvent`, `FeedResponse`, `EventKind`; `getDeviceKey(): string`; `api.getFeed(cursor?)`, `api.markSeen()`

- [ ] **Step 1: Append the types to `frontend/types.ts`**

```typescript
export type EventKind = "BIG_MOVE" | "VOLUME_SPIKE" | "RANGE_BREAK" | "GAP";

export interface FeedEvent {
  id: number;
  symbol: string;
  kind: EventKind;
  occurred_at: string;
  severity: 1 | 2 | 3;
  payload: Record<string, string | number>;
}

export interface FeedResponse {
  events: FeedEvent[];
  unread_count: number;
  last_seen_at: string;
  next_cursor: string | null;
}
```

- [ ] **Step 2: Write the device key module**

Create `frontend/lib/deviceKey.ts`:

```typescript
// frontend/lib/deviceKey.ts
// Identity is a random key kept in localStorage and exchanged for a user row
// server-side. Deliberately not authentication — it replaces the single
// global watchlist, it does not secure it.
const STORAGE_KEY = "since.deviceKey";

let cached: string | null = null;

function generate(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return `${crypto.randomUUID()}${crypto.randomUUID()}`.replace(/-/g, "");
  }
  return Array.from({ length: 48 }, () =>
    Math.floor(Math.random() * 36).toString(36)
  ).join("");
}

export function getDeviceKey(): string {
  if (cached) return cached;
  // Private windows and blocked site data both throw here; fall back to an
  // in-memory key so the session still works, it just will not persist.
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && stored.length >= 32) {
      cached = stored;
      return cached;
    }
    const fresh = generate();
    localStorage.setItem(STORAGE_KEY, fresh);
    cached = fresh;
    return cached;
  } catch {
    cached = cached ?? generate();
    return cached;
  }
}
```

- [ ] **Step 3: Send the key on every request in `frontend/lib/api.ts`**

Add the import:

```typescript
import { getDeviceKey } from "@/lib/deviceKey";
import { FeedResponse } from "@/types";
```

Replace `fetchJSON` with:

```typescript
async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { ...(options?.headers ?? {}), "X-Device-Key": getDeviceKey() },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}
```

Add to the `api` object:

```typescript
  getFeed: (cursor?: string) =>
    fetchJSON<FeedResponse>(`/feed${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`),
  markSeen: () =>
    fetchJSON<{ last_seen_at: string }>("/feed/seen", { method: "POST" }),
```

- [ ] **Step 4: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no output, exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/types.ts frontend/lib/deviceKey.ts frontend/lib/api.ts
git commit -m "feat: device key identity and feed API client"
```

---

## Task 12: The feed UI

**Files:**
- Create: `frontend/components/EventRow.tsx`
- Create: `frontend/components/Divider.tsx`
- Create: `frontend/components/Feed.tsx`
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes: `FeedEvent`, `FeedResponse`, `api.getFeed`, `api.markSeen`
- Produces: `<Feed onToggleSidebar={() => void} />`

- [ ] **Step 1: Write the narration and one row**

Create `frontend/components/EventRow.tsx`:

```tsx
import { FeedEvent } from "@/types";

const SEVERITY_DOT: Record<number, string> = {
  1: "bg-[#3a3a3a]",
  2: "bg-[#f59e0b]",
  3: "bg-[#ff5530]",
};

function num(value: unknown): number {
  return typeof value === "number" ? value : 0;
}

function signed(value: number, digits = 1): string {
  return `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(digits)}%`;
}

// Narration is a deterministic template per kind, filled from the payload the
// detector recorded. No generation at read time — the sentence a user sees
// must be reproducible from the row.
export function narrate(event: FeedEvent): string {
  const p = event.payload;
  switch (event.kind) {
    case "BIG_MOVE":
      return `Moved ${signed(num(p.move_pct))} — ${num(p.multiple).toFixed(1)}× its normal daily range`;
    case "VOLUME_SPIKE":
      return `Traded ${num(p.ratio).toFixed(1)}× its normal volume`;
    case "RANGE_BREAK":
      return p.scope === "52w"
        ? `New 52-week ${p.direction === "high" ? "high" : "low"}`
        : `Broke ${p.direction === "high" ? "above" : "below"} its 20-day range`;
    case "GAP":
      return `Gapped ${signed(num(p.gap_pct))} at the open`;
    default:
      return event.kind;
  }
}

export function chips(event: FeedEvent): string[] {
  const p = event.payload;
  switch (event.kind) {
    case "BIG_MOVE":
      return [signed(num(p.move_pct)), `${num(p.multiple).toFixed(1)}× range`];
    case "VOLUME_SPIKE":
      return [`${num(p.ratio).toFixed(1)}× vol`];
    case "RANGE_BREAK":
      return [`${p.scope} ${p.direction}`];
    case "GAP":
      return [`gap ${signed(num(p.gap_pct))}`];
    default:
      return [];
  }
}

export function EventRow({ event, unseen }: { event: FeedEvent; unseen: boolean }) {
  const time = new Date(event.occurred_at).toLocaleDateString("en-IN", {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <article
      className={`flex gap-3 px-4 py-3.5 border-b border-[#151515] transition-colors ${
        unseen ? "bg-[#0e0e0e]" : ""
      }`}
    >
      <div className={`w-1.5 h-1.5 rounded-full shrink-0 mt-2 ${SEVERITY_DOT[event.severity]}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <span
            className={`text-[12px] font-semibold tracking-tight ${
              unseen ? "text-white" : "text-[#8a8a8a]"
            }`}
          >
            {event.symbol}
          </span>
          <time className="text-[10px] text-[#3d3d3d] shrink-0">{time}</time>
        </div>
        <p className={`text-[12px] mt-0.5 ${unseen ? "text-[#c8c8c8]" : "text-[#5e5e5e]"}`}>
          {narrate(event)}
        </p>
        <div className="flex flex-wrap gap-1.5 mt-2">
          {chips(event).map((chip) => (
            <span
              key={chip}
              className="text-[10px] text-[#6a6a6a] bg-[#141414] border border-[#1e1e1e] rounded-full px-2 py-0.5 tabular-nums"
            >
              {chip}
            </span>
          ))}
        </div>
      </div>
    </article>
  );
}
```

- [ ] **Step 2: Write the divider**

Create `frontend/components/Divider.tsx`:

```tsx
// The whole product in one component: a line marking where the user stopped
// reading. Everything above it is new since their last visit.
export function Divider({ lastSeenAt }: { lastSeenAt: string }) {
  const label = new Date(lastSeenAt).toLocaleString("en-IN", {
    weekday: "long",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="flex items-center gap-3 px-4 py-3" role="separator">
      <div className="h-px flex-1 bg-[#ff5530]/25" />
      <span className="text-[10px] uppercase tracking-[0.12em] text-[#ff5530]/70 shrink-0">
        {label} — your last visit
      </span>
      <div className="h-px flex-1 bg-[#ff5530]/25" />
    </div>
  );
}
```

- [ ] **Step 3: Write the feed container**

Create `frontend/components/Feed.tsx`:

```tsx
"use client";
import { useCallback, useEffect, useState } from "react";
import { FeedEvent } from "@/types";
import { api } from "@/lib/api";
import { useInterval } from "@/hooks/useInterval";
import { EventRow } from "./EventRow";
import { Divider } from "./Divider";

export function Feed({ onToggleSidebar }: { onToggleSidebar: () => void }) {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [lastSeenAt, setLastSeenAt] = useState<string | null>(null);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.getFeed();
      setEvents(data.events);
      setLastSeenAt(data.last_seen_at);
      setUnread(data.unread_count);
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);
  useInterval(load, 120_000);

  async function catchUp() {
    try {
      const { last_seen_at } = await api.markSeen();
      setLastSeenAt(last_seen_at);
      setUnread(0);
    } catch {
      setFailed(true);
    }
  }

  const isUnseen = (event: FeedEvent) =>
    lastSeenAt !== null && event.occurred_at > lastSeenAt;
  const dividerIndex = events.findIndex((event) => !isUnseen(event));

  return (
    <main className="flex-1 flex flex-col overflow-hidden bg-[#0a0a0a]">
      <header className="px-4 md:px-6 py-4 border-b border-[#191919] flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="md:hidden flex flex-col gap-[5px] p-1 -ml-1 text-[#555] hover:text-[#888] transition-colors"
          aria-label="Toggle market sidebar"
        >
          <span className="block w-[18px] h-[1.5px] bg-current rounded-full" />
          <span className="block w-[18px] h-[1.5px] bg-current rounded-full" />
          <span className="block w-[18px] h-[1.5px] bg-current rounded-full" />
        </button>
        <h1 className="text-[15px] font-semibold text-white tracking-tight">Since</h1>
        {unread > 0 && (
          <span className="text-[10px] font-semibold text-[#ff5530] bg-[#ff5530]/10 border border-[#ff5530]/20 rounded-full px-2 py-0.5">
            {unread} new
          </span>
        )}
        <div className="flex-1" />
        {unread > 0 && (
          <button
            onClick={catchUp}
            className="text-[11px] text-[#777] hover:text-white border border-[#1e1e1e] hover:border-[#2e2e2e] rounded-full px-3 py-1 transition-all"
          >
            Catch up
          </button>
        )}
      </header>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-14 bg-[#111] rounded-xl animate-pulse" />
            ))}
          </div>
        ) : failed ? (
          <p className="text-center text-[12px] text-[#f59e0b] py-16">
            Could not reach the feed. Showing nothing rather than something stale.
          </p>
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-6">
            <p className="text-[15px] font-semibold text-[#c8c8c8]">All quiet.</p>
            <p className="text-[12px] text-[#4a4a4a] mt-1.5">
              Nothing crossed your thresholds
              {lastSeenAt
                ? ` since ${new Date(lastSeenAt).toLocaleDateString("en-IN", {
                    weekday: "long",
                  })}`
                : ""}
              .
            </p>
          </div>
        ) : (
          events.map((event, i) => (
            <div key={event.id}>
              {i === dividerIndex && lastSeenAt && <Divider lastSeenAt={lastSeenAt} />}
              <EventRow event={event} unseen={isUnseen(event)} />
            </div>
          ))
        )}
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Render it from `frontend/app/page.tsx`**

Replace the `NewsFeed` import with `import { Feed } from "@/components/Feed";` and change the `<NewsFeed ... />` element to:

```tsx
      <Feed onToggleSidebar={() => setSidebarOpen((v) => !v)} />
```

- [ ] **Step 5: Typecheck and build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: no type errors; build reports `✓ Compiled successfully` and two static routes.

- [ ] **Step 6: Verify against a running backend**

Start the API: `cd backend && ./venv/bin/uvicorn main:app --reload`
Start the frontend: `cd frontend && npm run dev`

Open http://localhost:3000. Expected: the header reads "Since"; with no events yet the quiet state reads "All quiet." Add a symbol, run `./venv/bin/python -m scripts.backfill`, hit `POST /admin/refresh` with the `CRON_SECRET` header, and reload — events appear with the divider below the unseen ones.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/EventRow.tsx frontend/components/Divider.tsx frontend/components/Feed.tsx frontend/app/page.tsx
git commit -m "feat: the feed, the divider and the quiet state"
```

---

## Self-Review Notes

**Spec coverage.** §4 data model → Task 1. §5 detectors → Tasks 2–3. §6 pipeline → Task 6. §7 identity → Tasks 7, 11. §8 API → Tasks 8, 9. §10 scale (news url constraint, indexed feed) → Tasks 1, 8. §11 defects: #2 admin auth → Task 9; #3 news duplicates → Task 1; #10 watchlist prices → deferred to Task 13 below. §13 Phase 1 items 1–6 → Tasks 1–12.

**Known gap carried forward.** Phase 1 item 7 — the priced watchlist sidebar with staleness badges and the market-status chip — is **not** covered by Tasks 1–12. It depends on nothing from them and is a self-contained follow-up (`Sidebar.tsx`, `PriceRow.tsx`, plus an `as_of` field on `/market`). Track it as **Task 13** and write it once Tasks 1–12 are green, so the plan does not grow a placeholder.

**Defects deliberately not fixed in Phase 1** (spec §11 items 4–9): the `published_at` NULL ordering, the dead ticker stat cells, the `$`-on-INR bug, Telegram Markdown escaping, the UTC/IST digest header, and the `CORS_ORIGINS` default. None block the feed. They belong with Phase 3, when the digest is rewritten to read from `events`.

**Type consistency check.** `Bar`, `SymbolStats` and `DetectedEvent` are defined once in Task 2 and consumed unchanged in Tasks 3, 4, 5 and 6. `detect()`'s signature in Task 3 matches its call site in Task 6. `current_user` from Task 7 is the dependency overridden in Tasks 8 and 9. `FeedResponse` in Task 11 matches the `GET /feed` body in Task 8 field for field.
