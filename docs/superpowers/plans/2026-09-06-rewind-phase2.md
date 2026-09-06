# Rewind (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user scrub one selected watchlist symbol's own chart from their last visit to now, inside the existing `TickerModal` drawer.

**Architecture:** One new read-only endpoint (`GET /history`) returns a single symbol's daily closes between `last_seen_at` and now, reusing the `price_snapshots` table and `current_user`/`get_watchlist`/`get_last_seen` machinery Phase 1 already built. The frontend renders that series as a small hand-rolled SVG line inside a new `RewindScrubber` component, mounted only inside `TickerModal` — nothing else on the sidebar re-renders when it's open.

**Tech Stack:** FastAPI + Supabase (existing), Next.js/React + inline SVG (no new dependency — the codebase has no charting library and none is needed for one line).

## Global Constraints

- Per the 2026-09-06 revision of `docs/superpowers/specs/2026-09-05-smart-watchlist-design.md` §13: Rewind is scoped to **one symbol at a time**, never the whole board. Do not build any cross-symbol or page-level scrubber state.
- `GET /history` takes a single `symbol` query param (not `symbols`), matching the revised spec.
- No new database tables. `price_snapshots` (already populated by Phase 1's refresh pipeline) is the only data source.
- No new auth. Reuse `identity.current_user`, exactly as `routes/feed.py` and `routes/watchlist.py` already do.
- The default scrub range is `last_seen_at` (from `get_last_seen`) through now — "a replay of your absence," not an arbitrary date-range chart. `from`/`to` query params exist only to override this default explicitly; nothing in this plan needs to pass them.
- The `┊` last-visit marker is always the chart's left edge, because the range itself always starts at `last_seen_at` — this is correct, not a bug, and no task should try to show "before" context.
- Frontend has no test infrastructure (established project convention) — the frontend task is verified via `npm run build` (TypeScript is the safety net) plus a live manual check, not automated tests.

---

### Task 1: `GET /history` backend endpoint

**Files:**
- Modify: `backend/database.py` — add `get_snapshot_range`
- Create: `backend/routes/history.py`
- Modify: `backend/main.py` — register the router
- Test: `backend/tests/test_database.py` (append)
- Test: `backend/tests/test_history_routes.py` (create)

**Interfaces:**
- Consumes: `database.get_last_seen(user_id) -> str`, `database.get_watchlist(user_id) -> list[dict]` (existing, both already used by `routes/feed.py`), `identity.current_user` (existing FastAPI dependency).
- Produces: `database.get_snapshot_range(symbol: str, from_ts: str, to_ts: str) -> list[dict]` where each dict is `{"ts": str, "close": float}`, oldest-first. `GET /history?symbol=` response body: `{"symbol": str, "last_seen_at": str, "bars": list[dict]}`.

- [ ] **Step 1: Write the failing tests for `get_snapshot_range`**

Append to `backend/tests/test_database.py`:

```python
def test_get_snapshot_range_returns_bars_as_ts_close_dicts():
    rows = [
        {"ts": "2026-01-01T00:00:00+00:00", "close": 1},
        {"ts": "2026-01-02T00:00:00+00:00", "close": 2},
    ]
    with patch("database.get_client") as client:
        chain = (client.return_value.table.return_value.select.return_value
                  .eq.return_value.gte.return_value.lte.return_value)
        chain.order.return_value.execute.return_value = MagicMock(data=rows)
        bars = database.get_snapshot_range(
            "X", "2026-01-01T00:00:00+00:00", "2026-01-02T23:59:59+00:00")
    assert bars == [
        {"ts": "2026-01-01T00:00:00+00:00", "close": 1.0},
        {"ts": "2026-01-02T00:00:00+00:00", "close": 2.0},
    ]


def test_get_snapshot_range_queries_the_given_symbol_and_window_ascending():
    table = MagicMock()
    with patch("database.get_client") as client:
        client.return_value.table.return_value = table
        chain = table.select.return_value.eq.return_value.gte.return_value.lte.return_value
        chain.order.return_value.execute.return_value = MagicMock(data=[])
        database.get_snapshot_range(
            "RELIANCE.NS", "2026-01-01T00:00:00+00:00", "2026-01-05T00:00:00+00:00")
    table.select.return_value.eq.assert_called_once_with("symbol", "RELIANCE.NS")
    table.select.return_value.eq.return_value.gte.assert_called_once_with(
        "ts", "2026-01-01T00:00:00+00:00")
    table.select.return_value.eq.return_value.gte.return_value.lte.assert_called_once_with(
        "ts", "2026-01-05T00:00:00+00:00")
    chain.order.assert_called_once_with("ts")


def test_get_snapshot_range_skips_rows_with_no_close():
    rows = [
        {"ts": "2026-01-01T00:00:00+00:00", "close": None},
        {"ts": "2026-01-02T00:00:00+00:00", "close": 3},
    ]
    with patch("database.get_client") as client:
        chain = (client.return_value.table.return_value.select.return_value
                  .eq.return_value.gte.return_value.lte.return_value)
        chain.order.return_value.execute.return_value = MagicMock(data=rows)
        bars = database.get_snapshot_range(
            "X", "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00")
    assert bars == [{"ts": "2026-01-02T00:00:00+00:00", "close": 3.0}]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_database.py -k snapshot_range -v`
Expected: FAIL with `AttributeError: module 'database' has no attribute 'get_snapshot_range'`

- [ ] **Step 3: Implement `get_snapshot_range`**

Add to `backend/database.py`, directly below the existing `get_snapshots` function:

```python
def get_snapshot_range(symbol: str, from_ts: str, to_ts: str) -> list[dict]:
    """Daily closes for one symbol between two timestamps, inclusive,
    oldest-first. Feeds the Rewind scrubber's chart — unlike `get_snapshots`,
    callers here only need a close price to plot, not a full OHLCV bar."""
    res = (get_client().table("price_snapshots")
           .select("ts, close")
           .eq("symbol", symbol)
           .gte("ts", from_ts)
           .lte("ts", to_ts)
           .order("ts")
           .execute())
    return [{"ts": r["ts"], "close": float(r["close"])}
            for r in (res.data or []) if r.get("close") is not None]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_database.py -k snapshot_range -v`
Expected: 3 passed

- [ ] **Step 5: Write the failing tests for `GET /history`**

Create `backend/tests/test_history_routes.py`:

```python
# backend/tests/test_history_routes.py
from unittest.mock import patch

from fastapi.testclient import TestClient

from identity import MIN_KEY_LENGTH, current_user
from main import app

client = TestClient(app)
HEADERS = {"X-Device-Key": "k" * MIN_KEY_LENGTH}


def _as_user(user_id="u1"):
    app.dependency_overrides[current_user] = lambda: {"id": user_id}


def teardown_function():
    app.dependency_overrides.clear()


def test_history_requires_a_device_key():
    assert client.get("/history?symbol=RELIANCE.NS").status_code == 401


def test_history_404s_for_a_symbol_not_on_the_callers_watchlist():
    _as_user()
    with patch("routes.history.get_watchlist", return_value=[{"symbol": "TCS.NS"}]):
        resp = client.get("/history?symbol=RELIANCE.NS", headers=HEADERS)
    assert resp.status_code == 404


def test_history_defaults_the_range_to_last_seen_through_now():
    _as_user()
    with patch("routes.history.get_watchlist", return_value=[{"symbol": "RELIANCE.NS"}]), \
         patch("routes.history.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.history._utc_now_iso", return_value="2026-03-05T00:00:00+00:00"), \
         patch("routes.history.get_snapshot_range", return_value=[]) as getter:
        client.get("/history?symbol=RELIANCE.NS", headers=HEADERS)
    getter.assert_called_once_with(
        "RELIANCE.NS", "2026-03-01T00:00:00+00:00", "2026-03-05T00:00:00+00:00")


def test_history_lets_explicit_from_and_to_override_the_defaults():
    _as_user()
    with patch("routes.history.get_watchlist", return_value=[{"symbol": "RELIANCE.NS"}]), \
         patch("routes.history.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.history.get_snapshot_range", return_value=[]) as getter:
        client.get(
            "/history?symbol=RELIANCE.NS&from=2026-02-01T00:00:00%2B00:00"
            "&to=2026-02-15T00:00:00%2B00:00",
            headers=HEADERS,
        )
    getter.assert_called_once_with(
        "RELIANCE.NS", "2026-02-01T00:00:00+00:00", "2026-02-15T00:00:00+00:00")


def test_history_returns_last_seen_at_and_bars():
    _as_user()
    bars = [{"ts": "2026-03-02T00:00:00+00:00", "close": 1432.1}]
    with patch("routes.history.get_watchlist", return_value=[{"symbol": "RELIANCE.NS"}]), \
         patch("routes.history.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.history.get_snapshot_range", return_value=bars):
        resp = client.get("/history?symbol=RELIANCE.NS", headers=HEADERS)
    body = resp.json()
    assert resp.status_code == 200
    assert body["symbol"] == "RELIANCE.NS"
    assert body["last_seen_at"] == "2026-03-01T00:00:00+00:00"
    assert body["bars"] == bars


def test_history_uppercases_the_symbol_before_checking_ownership():
    _as_user()
    with patch("routes.history.get_watchlist", return_value=[{"symbol": "RELIANCE.NS"}]), \
         patch("routes.history.get_last_seen", return_value="2026-03-01T00:00:00+00:00"), \
         patch("routes.history.get_snapshot_range", return_value=[]) as getter:
        resp = client.get("/history?symbol=reliance.ns", headers=HEADERS)
    assert resp.status_code == 200
    assert getter.call_args[0][0] == "RELIANCE.NS"
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_history_routes.py -v`
Expected: FAIL — `/history` does not exist yet (404s that the tests expect elsewhere, or import errors)

- [ ] **Step 7: Implement the route**

Create `backend/routes/history.py`:

```python
# backend/routes/history.py
"""Rewind: replay one symbol's own chart from the user's last visit to now.

Scoped to a single symbol per request, not the whole board — selecting a
symbol reveals its own scrubber; nothing else on the sidebar re-renders.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from database import get_last_seen, get_snapshot_range, get_watchlist
from identity import current_user

router = APIRouter()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/history")
def history(
    symbol: str = Query(...),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    user: dict = Depends(current_user),
):
    symbol = symbol.upper()
    watched = {row["symbol"] for row in get_watchlist(user["id"])}
    if symbol not in watched:
        raise HTTPException(status_code=404, detail="Symbol not on your watchlist")

    last_seen_at = get_last_seen(user["id"])
    # The scrubbable range defaults to "since you last checked" — a replay
    # of your absence, not an arbitrary date-range chart.
    range_from = from_ or last_seen_at
    range_to = to or _utc_now_iso()
    bars = get_snapshot_range(symbol, range_from, range_to)
    return {"symbol": symbol, "last_seen_at": last_seen_at, "bars": bars}
```

- [ ] **Step 8: Register the router**

Modify `backend/main.py`. Change:

```python
from routes.feed import router as feed_router
from routes.market import router as market_router
```

to:

```python
from routes.feed import router as feed_router
from routes.history import router as history_router
from routes.market import router as market_router
```

And change:

```python
app.include_router(telegram_router)
app.include_router(feed_router)
```

to:

```python
app.include_router(telegram_router)
app.include_router(feed_router)
app.include_router(history_router)
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_history_routes.py -v`
Expected: 6 passed

- [ ] **Step 10: Run the full backend suite**

Run: `cd backend && pytest`
Expected: all tests pass, no regressions

- [ ] **Step 11: Commit**

```bash
git add backend/database.py backend/routes/history.py backend/main.py \
        backend/tests/test_database.py backend/tests/test_history_routes.py
git commit -m "feat: add GET /history for the per-symbol Rewind scrubber"
```

---

### Task 2: Frontend `RewindScrubber` component

**Files:**
- Modify: `frontend/types.ts` — add `HistoryBar`, `HistoryResponse`
- Modify: `frontend/lib/api.ts` — add `getHistory`
- Create: `frontend/components/RewindScrubber.tsx`
- Modify: `frontend/components/TickerModal.tsx` — mount it

**Interfaces:**
- Consumes: `GET /history?symbol=` from Task 1, returning `{symbol, last_seen_at, bars: [{ts, close}]}`.
- Produces: `<RewindScrubber symbol={string} />`, a self-contained component with its own loading/fetch state — no props beyond `symbol`, no shared state with any sibling component.

- [ ] **Step 1: Add the response types**

Modify `frontend/types.ts`. Add after the existing `FeedResponse` interface:

```typescript
export interface HistoryBar {
  ts: string;
  close: number;
}

export interface HistoryResponse {
  symbol: string;
  last_seen_at: string;
  bars: HistoryBar[];
}
```

- [ ] **Step 2: Add the API call**

Modify `frontend/lib/api.ts`. Change the import line:

```typescript
import { MarketPrice, NewsItem, WatchlistItem, NewsCategory, WatchlistType, SearchResult, TickerDetail, SymbolNewsResponse } from "@/types";
```

to:

```typescript
import { MarketPrice, NewsItem, WatchlistItem, NewsCategory, WatchlistType, SearchResult, TickerDetail, SymbolNewsResponse, HistoryResponse } from "@/types";
```

Add to the `api` object, after `markNewsSeen`:

```typescript
  getHistory: (symbol: string) =>
    fetchJSON<HistoryResponse>(`/history?symbol=${encodeURIComponent(symbol)}`),
```

- [ ] **Step 3: Build the component**

Create `frontend/components/RewindScrubber.tsx`:

```tsx
"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { HistoryBar } from "@/types";
import { api } from "@/lib/api";

const PLAY_STEP_MS = 400;
const CHART_HEIGHT = 64;

interface Props {
  symbol: string;
}

export function RewindScrubber({ symbol }: Props) {
  const [bars, setBars] = useState<HistoryBar[]>([]);
  const [lastSeenAt, setLastSeenAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const playRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.getHistory(symbol)
      .then((data) => {
        if (cancelled) return;
        setBars(data.bars);
        setLastSeenAt(data.last_seen_at);
        setIndex(data.bars.length > 0 ? data.bars.length - 1 : 0);
      })
      .catch(() => { if (!cancelled) setBars([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [symbol]);

  // Play steps the handle forward one day at a time until it reaches the
  // end, so the line "grows" and reads as a replay rather than a jump-cut.
  useEffect(() => {
    if (!playing) return;
    playRef.current = setInterval(() => {
      setIndex((i) => {
        if (i >= bars.length - 1) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, PLAY_STEP_MS);
    return () => { if (playRef.current) clearInterval(playRef.current); };
  }, [playing, bars.length]);

  const visible = bars.slice(0, index + 1);

  const points = useMemo(() => {
    if (visible.length < 2) return "";
    const closes = visible.map((b) => b.close);
    const min = Math.min(...closes);
    const max = Math.max(...closes);
    const span = max - min || 1;
    const width = 100;
    return visible
      .map((b, i) => {
        const x = (i / (visible.length - 1)) * width;
        const y = CHART_HEIGHT - ((b.close - min) / span) * CHART_HEIGHT;
        return `${x},${y.toFixed(2)}`;
      })
      .join(" ");
  }, [visible]);

  if (loading) {
    return <div className="h-24 bg-[#161616] border border-[#1e1e1e] rounded-xl animate-pulse" />;
  }

  if (bars.length < 2) {
    return (
      <div className="bg-[#161616] border border-[#1e1e1e] rounded-xl p-3">
        <p className="text-[11px] text-[#444]">Not enough history yet to rewind {symbol}.</p>
      </div>
    );
  }

  const current = bars[index];

  return (
    <div className="bg-[#161616] border border-[#1e1e1e] rounded-xl p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] text-[#555] uppercase tracking-wider">Rewind</span>
        <span className="text-[11px] text-[#888] tabular-nums">
          {new Date(current.ts).toLocaleDateString("en-IN", { month: "short", day: "numeric" })}
          {" · "}
          {current.close.toLocaleString("en-US", { maximumFractionDigits: 2 })}
        </span>
      </div>

      <svg viewBox={`0 0 100 ${CHART_HEIGHT}`} preserveAspectRatio="none" className="w-full h-16">
        {/* The last-visit marker: bars[0] IS last_seen_at, since the range
            always starts there — so it always sits at the chart's left edge. */}
        <line x1={0} y1={0} x2={0} y2={CHART_HEIGHT} stroke="#3a3a3a" strokeDasharray="2,2" strokeWidth={1} />
        {points && (
          <polyline points={points} fill="none" stroke="#22c55e" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
        )}
      </svg>

      <div className="flex items-center gap-2 mt-2">
        <button
          onClick={() => setPlaying((p) => !p)}
          className="text-[11px] text-[#888] hover:text-white transition-colors w-5 text-center shrink-0"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? "⏸" : "▶"}
        </button>
        <input
          type="range"
          min={0}
          max={bars.length - 1}
          value={index}
          onChange={(e) => { setPlaying(false); setIndex(Number(e.target.value)); }}
          className="flex-1 accent-[#22c55e]"
        />
      </div>
      {lastSeenAt && (
        <p className="text-[9px] text-[#3a3a3a] mt-1">
          Since your last visit — {new Date(lastSeenAt).toLocaleDateString("en-IN", { month: "short", day: "numeric" })}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Mount it in `TickerModal`**

Modify `frontend/components/TickerModal.tsx`. Change the import block:

```tsx
import { useEffect, useState } from "react";
import { TickerDetail, WatchlistType } from "@/types";
import { api } from "@/lib/api";
```

to:

```tsx
import { useEffect, useState } from "react";
import { TickerDetail, WatchlistType } from "@/types";
import { api } from "@/lib/api";
import { RewindScrubber } from "./RewindScrubber";
```

Change:

```tsx
                <div className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-[12px] font-semibold mb-1 ${
                  isUp ? "bg-[#22c55e]/10 text-[#22c55e]" : "bg-[#ef4444]/10 text-[#ef4444]"
                }`}>
                  {isUp ? "▲" : "▼"} {Math.abs(data.change_pct).toFixed(2)}%
                  <span className="opacity-70 ml-0.5">
                    ({isUp ? "+" : ""}{fmt(data.change_abs, 2)})
                  </span>
                </div>
              </div>

              {/* Stats grid */}
```

to:

```tsx
                <div className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-[12px] font-semibold mb-1 ${
                  isUp ? "bg-[#22c55e]/10 text-[#22c55e]" : "bg-[#ef4444]/10 text-[#ef4444]"
                }`}>
                  {isUp ? "▲" : "▼"} {Math.abs(data.change_pct).toFixed(2)}%
                  <span className="opacity-70 ml-0.5">
                    ({isUp ? "+" : ""}{fmt(data.change_abs, 2)})
                  </span>
                </div>
              </div>

              <RewindScrubber symbol={symbol} />

              {/* Stats grid */}
```

- [ ] **Step 5: Type-check**

Run: `cd frontend && npm run build`
Expected: build succeeds, no TypeScript errors

- [ ] **Step 6: Verify live**

No frontend test infrastructure exists in this project (established convention), so this step is a manual live check, matching how every other Phase 1/news-feed frontend change in this project was verified:

Run: `cd frontend && npm run dev`, open the app, click any existing watchlist symbol to open its drawer, and confirm:
- A "Rewind" panel appears below the price block with a chart, a play button, and a range slider.
- Dragging the slider redraws the line up to that point and updates the date/price readout.
- Pressing play animates the slider forward on its own and stops at the end.
- If the symbol has fewer than 2 snapshots, the panel reads "Not enough history yet to rewind {symbol}" instead of an empty chart.

- [ ] **Step 7: Commit**

```bash
git add frontend/types.ts frontend/lib/api.ts frontend/components/RewindScrubber.tsx \
        frontend/components/TickerModal.tsx
git commit -m "feat: add per-symbol Rewind scrubber to the ticker drawer"
```
