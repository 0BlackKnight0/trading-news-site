# Smart Market Watchlist — Design

**Date:** 2026-09-05
**Status:** Approved, ready for implementation planning
**Brief:** CODE 2026 — "Build a Smart Market Watchlist"

---

## 1. Thesis

Every watchlist is a **scoreboard**: all rows, always visible, equally weighted. The
brief asks for something else — *"understand what has meaningfully changed since
they last checked."* That is not a scoreboard, it is a **diff**.

So: the watchlist keeps a **changelog**, and a single divider marks where the user
stopped reading. Slack's "new messages" line, applied to markets.

The product is named **Since**.

Two concepts ship in sequence:

- **The Line** (Phase 1) — an append-only event log with an unread divider.
- **Rewind** (Phase 2) — a time scrubber that replays the board from the user's
  last visit to now, on the same snapshot data.

A third concept — a weighted composite "Signal Score" with suppression and an
attention budget — was explored and deliberately **deferred as too complex for the
timeline**. It is recorded in section 12 as the natural successor, and the schema
here does not preclude it.

---

## 2. How this answers the brief

| Brief requirement | Answer |
| --- | --- |
| Create and manage a watchlist | User-scoped `watchlist`, with prices, pin and mute on every row |
| View latest market information | Priced sidebar + symbol drawer, every value carrying provenance |
| **Return later and see what changed** | The event log + `last_seen_at` divider + the `┊` marker on every sparkline |
| What counts as a meaningful change | Five threshold detectors, measured against each symbol's *own* behaviour (§5) |
| What information to surface | Only events that cross a threshold. The absence of a row is a decision |
| State across sessions/devices | Server-side `user_state.last_seen_at`; device key + 6-char sync code (§7) |
| Stale, delayed, conflicting data | Provenance on every price, visible degradation, market-hours awareness (§9) |
| Scale | Precomputed stats, O(1) detectors, indexed feed query, idempotent writes (§10) |
| Simple vs complex | Thresholds instead of a weighted score. Pure detector functions. No LLM in the hot path |

---

## 3. Architecture

Keep the existing shell — Next.js 16 (App Router) frontend, FastAPI on Vercel
serverless, Supabase Postgres, and the working direct-to-Yahoo chart client in
`backend/aggregator/yahoo.py`. Rebuild the data layer beneath it.

```
Yahoo chart API ──> refresh pipeline ──> price_snapshots
                          │                    │
                          │                    v
                          │              symbol_stats  (rolling, per refresh)
                          │                    │
                          └────> detect() <────┘   (pure, no I/O)
                                    │
                                    v
                                 events  (append-only, idempotent)
                                    │
                        ┌───────────┴───────────┐
                        v                       v
                   GET /feed              Telegram digest
                   (web UI)               (same engine)
```

One engine, two surfaces. The digest is not a second feature; it is the feed with
a different output adapter.

---

## 4. Data model

### Retained from the current build

- `market_cache` — latest-quote fast path, unchanged shape
- `news_cache` — retained; the duplicate-insert bug is fixed in §10
- `refresh_meta` — retained; the on-read revalidation design is sound
- `telegram_users` — gains a `user_id` foreign key
- `watchlist` — gains a `user_id` foreign key. The old `symbol TEXT UNIQUE`
  constraint is dropped and replaced by `UNIQUE (user_id, symbol)`, so two users
  can watch the same symbol

### New tables

```sql
CREATE TABLE users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_key  TEXT UNIQUE NOT NULL,
  sync_code   TEXT UNIQUE,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- Append-only daily bars. Backfilled one year on first symbol add.
CREATE TABLE price_snapshots (
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
CREATE INDEX ON price_snapshots (symbol, ts DESC);

-- Rolling statistics, recomputed once per refresh so detectors stay O(1).
CREATE TABLE symbol_stats (
  symbol           TEXT PRIMARY KEY,
  avg_daily_range  NUMERIC,   -- 20d mean of (high-low)/close
  avg_volume_20d   BIGINT,
  vol_30d          NUMERIC,   -- stdev of 30d daily returns
  high_52w         NUMERIC,
  low_52w          NUMERIC,
  high_20d         NUMERIC,
  low_20d          NUMERIC,
  computed_at      TIMESTAMPTZ DEFAULT now()
);

-- The changelog. The existence of a row IS the judgment.
CREATE TABLE events (
  id           BIGSERIAL PRIMARY KEY,
  symbol       TEXT NOT NULL,
  kind         TEXT NOT NULL,     -- BIG_MOVE|VOLUME_SPIKE|RANGE_BREAK|GAP|ALERT
  occurred_at  TIMESTAMPTZ NOT NULL,
  severity     SMALLINT NOT NULL DEFAULT 1,   -- 1..3
  payload      JSONB NOT NULL,    -- the numbers behind the claim
  dedupe_key   TEXT UNIQUE NOT NULL,          -- 'RELIANCE|RANGE_BREAK|2026-09-05'
  created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON events (occurred_at DESC);
CREATE INDEX ON events (symbol, occurred_at DESC);

CREATE TABLE user_state (
  user_id       UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_symbol_state (
  user_id       UUID REFERENCES users(id) ON DELETE CASCADE,
  symbol        TEXT NOT NULL,
  muted         BOOLEAN NOT NULL DEFAULT false,
  min_move_pct  NUMERIC,          -- extra floor on BIG_MOVE, NULL = none
  pinned        BOOLEAN NOT NULL DEFAULT false,
  PRIMARY KEY (user_id, symbol)
);
```

### Design notes

**`dedupe_key UNIQUE` makes the whole pipeline idempotent.** Detectors re-run on
every refresh and re-inserting is a harmless conflict. This matters because Vercel
cron invocations may duplicate, and because the current `insert_news` has exactly
this bug — it dedupes in Python against a PostgREST-capped 1000-row select.

**`symbol_stats` is what keeps detection cheap.** Rolling statistics are computed
once per refresh, not once per comparison, so a 500-symbol watchlist costs one
stats pass rather than a quadratic scan.

**Backfill is not optional.** An empty `price_snapshots` means no stats, therefore
no detectors, therefore an empty feed — and nothing for the Rewind scrubber to
move through. One Yahoo chart call per symbol (`range=1y&interval=1d`) fills it.

---

## 5. The detector — where "meaningful" is defined

New module `backend/signals/detect.py`. The defining property is that it is
**pure**: no database, no HTTP, no clock.

```python
def detect(
    latest: Bar,
    prev: Bar,
    stats: SymbolStats,
    overrides: ThresholdOverrides | None = None,
) -> list[Event]:
    ...
```

This is the single most important design decision in the spec. The definition of
"meaningful change" — the thing the brief cares most about — becomes table-driven
unit-testable against synthetic bars, with no fixtures and no mocking.

### The five detectors

| Kind | Rule | Severity |
| --- | --- | --- |
| `BIG_MOVE` | `abs(close/prev_close - 1) > 2 x avg_daily_range` | 1 at 2x, 2 at 3x, 3 at 4x+ |
| `VOLUME_SPIKE` | `volume > 2 x avg_volume_20d` | 1 at 2x, 2 at 3x, 3 at 5x+ |
| `RANGE_BREAK` | `close > high_52w` or `< low_52w`; else outside 20d box | 3 for 52w, 1 for 20d |
| `GAP` | `abs(open/prev_close - 1) > 0.015` | 1 at 1.5%, 2 at 3%, 3 at 5%+ |
| `ALERT` | user-set price crossed since previous bar | always 3 |

`BIG_MOVE` is measured against **the symbol's own average daily range**, not a flat
percentage. A 2% day means something different for HDFC Bank than for a mid-cap
coin. This is the defensible core of the answer to "what counts as meaningful,"
and it costs one division.

`min_move_pct` in `user_symbol_state` is an **additional floor**, not a replacement:
when set, `BIG_MOVE` fires only if the move clears both the 2x average-daily-range
rule and this absolute percentage. It exists so a user can say "don't wake me for
TSLA unless it moves 5%" without having to reason about volatility multiples.
`muted` suppresses all non-`ALERT` events for that symbol.

Because detection is global and thresholds are per-user, detectors run **unfiltered**
and write every event once; per-user overrides are applied at read time in `/feed`.
This keeps the write path independent of user count.

### Payload and narration

Every event stores its numbers:

```json
{ "close": 1432.10, "prev_close": 1348.00, "move_pct": 6.24,
  "avg_daily_range": 0.021, "multiple": 2.97 }
```

The UI renders a **deterministic template per event kind**, filled from `payload`,
plus the same payload as evidence chips. No LLM in the hot path — narration must be
reproducible and debuggable.

---

## 6. Refresh pipeline

```
for each symbol on any watchlist:
    bars   = yahoo.fetch_chart(symbol, interval=1d, range=5d)
    upsert price_snapshots            (ON CONFLICT (symbol, ts) DO NOTHING)
    stats  = recompute_stats(symbol)  (from last 252 snapshots)
    upsert symbol_stats
    events = detect(latest, prev, stats)
    insert events                     (ON CONFLICT (dedupe_key) DO NOTHING)
```

Triggered by the existing on-read revalidation in `aggregator_loop.py` (15-minute
TTL via `refresh_meta`) and by `/cron/daily`. Both paths are safe to run
concurrently because every write is idempotent.

Retain the existing `_local_refresh` per-instance memo — it is a good answer to
warm-invocation cost and it caps damage when `refresh_meta` is unreachable.

---

## 7. Identity

A device key generated client-side, stored in `localStorage`, sent as
`X-Device-Key`. Middleware resolves it to a `users` row, creating one on first
contact. No login screen, no password handling, no email provider.

Cross-device is handled by a **6-character sync code**: settings on device B accepts
the code shown on device A, and both device keys map to the same `user_id`.

**Tradeoff accepted:** this is not authentication. Anyone holding a device key or a
live sync code is that user. For a personal dashboard that is the right trade;
upgrading to magic-link auth later means adding an `email` column and a verification
route, with no change to any other table.

**This closes a real hole in the current build,** where `watchlist` is global and
unauthenticated — any visitor can add or delete any symbol.

---

## 8. API surface

| Route | Purpose |
| --- | --- |
| `GET /feed?limit=&cursor=&since=` | Events newest-first, with `unread_count` and `last_seen_at`. `cursor` paginates (opaque, encodes `occurred_at` **and `id`**); `since` optionally overrides the divider baseline, defaulting to the caller's `last_seen_at` |
| `POST /feed/seen` | Sets `last_seen_at = now()` — the "catch up" action |
| `GET /history?symbols=&from=&to=` | Snapshot series for sparklines and the scrubber |
| `GET /watchlist` `POST` `DELETE` | Now user-scoped |
| `PATCH /watchlist/{symbol}` | Pin, mute, per-symbol threshold |
| `GET /ticker/{symbol}` | Retained; dead cells and the currency bug fixed (§11) |
| `GET /search?q=` | Retained; `q` URL-encoded server-side |
| `GET /cron/daily` | Retained; digest now composed from each user's unseen events |
| `POST /telegram/webhook` | Retained unchanged |
| `POST /admin/refresh` | **Now requires `CRON_SECRET`** — currently unauthenticated |

`/feed` is paginated by cursor on `occurred_at` so a long-dormant user does not pull
their entire history in one response.

---

## 9. Stale, delayed and conflicting data

The current build displays *"Live · Auto-refreshes every 60s"* while the backend TTL
is 15 minutes and the cron may not have run for a day. The design inverts this into
visible honesty:

- **Every price carries `as of HH:MM`** plus a `delayed 15m` badge.
- **Market status chip** — `NSE open · closes in 2h 14m` / `NSE closed · opens in
  3h 12m`, derived from Yahoo `meta.regularMarketTime` and the exchange timezone.
- **Visible degradation** — when a refresh fails, the row shows amber
  `⚠ last good 2h ago` rather than a silently stale number. Replaces the current
  blanket `except: return []`.
- **Conflicting sources** — `price_snapshots.source` records provenance. When the
  chart series and quote metadata disagree beyond 0.5%, the chart series wins
  (it is the one the detectors run on) and the row is flagged.
- **Feeds that fail are reported, not hidden.** Four of the eleven configured RSS
  feeds are currently dead or blocking: both Reuters endpoints (connection failure),
  Moneycontrol (403 on the bot User-Agent), and VentureBeat (429). Dead feeds get
  removed; live failures surface in the admin response.

---

## 10. Scale

- **Detectors are O(1) per symbol** against precomputed `symbol_stats`.
- **Feed reads are one indexed query per user** on `events (occurred_at DESC)`,
  cursor-paginated on the composite key `(occurred_at, id)`. The composite is
  required, not defensive: `occurred_at` is a market bar timestamp, so every
  symbol on the same exchange session shares an identical value — verified
  against live data, where RELIANCE.NS, TCS.NS and INFY.NS all report
  `2026-09-04T03:45:00+00:00`. A cursor on `occurred_at` alone would skip an
  entire tied group whenever a page boundary landed inside one.
- **Snapshot retention** — one year of daily bars per symbol, pruned on a rolling
  window. Storage per symbol is bounded and small.
- **Yahoo fetches stay pooled** through the existing `ThreadPoolExecutor`, capped per
  invocation so a large watchlist cannot exceed the function duration budget.
- **`insert_news` full-table scan is replaced** by a `UNIQUE (url)` constraint and
  `ON CONFLICT DO NOTHING`. The current implementation loads every title in the
  table on each refresh and silently starts inserting duplicates past 1000 rows,
  because `news_cache.title` has no unique constraint.
- **`news_cache` gains a retention window** — it currently grows forever.

---

## 11. Defects in the current build fixed as part of this work

1. Supabase-backed endpoints return 500 in production (`/market`, `/news`,
   `/watchlist`) while Yahoo-backed routes work — environment configuration on the
   `trading-news-api` Vercel project must be verified before anything else ships.
2. `POST /admin/refresh` is unauthenticated.
3. `news_cache` duplicate inserts past the PostgREST row cap; no pruning.
4. `get_news` orders `published_at DESC` with no NULLS clause, so undated articles
   sort *above* fresh ones and can fill the 20-row window.
5. `ticker.pe_ratio` is never assigned and `market_cap` is absent from chart
   metadata — both cells render a permanent `—`. Replaced with the stats the
   detectors actually use.
6. `TickerModal` hardcodes a `$` prefix on 52W High/Low and Prev Close regardless of
   `data.currency`.
7. Telegram digest interpolates raw headlines into Markdown links; a title
   containing `[`, `]`, `*` or `_` breaks the send. Switch to MarkdownV2 with
   escaping.
8. Digest header uses `datetime.now()`, which is UTC on Vercel, while claiming IST.
9. `CORS_ORIGINS` defaults to `*`.
10. Watchlist rows show no prices.

---

## 12. Out of scope (deliberately)

- **The Signal Score engine** — weighted composite of six signals, ranked
  suppression, narrated cards, attention budget. Deferred as too complex for the
  timeline. The `events.severity` and `payload` columns are forward-compatible with
  it: scoring becomes a read-time ranking over rows this design already writes.
- **Real authentication.** See §7.
- **Intraday granularity.** Daily bars only, so the Rewind scrubber moves day by
  day. Intraday would multiply snapshot volume by ~400x for marginal benefit at
  this scope.
- **News entity-linking to watchlist symbols.** Valuable, but Phase 3+.
- **Portfolio tracking** — quantities, cost basis, P&L. Not asked for by the brief.

---

## 13. Phasing

Each phase is independently shippable.

**Phase 1 — The Line**
1. Schema migration; backfill script for one year of daily bars
2. `signals/detect.py` — pure detectors, table-driven unit tests
3. Refresh pipeline: fetch → snapshot → stats → detect → events
4. Device-key identity middleware; user-scoped watchlist
5. `GET /feed`, `POST /feed/seen`
6. Feed UI: event rows, the divider, catch-up, quiet state
7. Priced watchlist sidebar; staleness badges; market-status chip

**Phase 2 — Rewind**
8. `GET /history`
9. Scrubber component with animated replay
10. `┊` last-visit marker on every sparkline

**Phase 3 — Delivery and control**
11. Telegram digest composed from unseen events, MarkdownV2-escaped
12. Pin, mute and per-symbol thresholds
13. Sync code for cross-device

---

## 14. Testing

- **Detectors carry the test weight.** Pure functions, synthetic `Bar` fixtures,
  table-driven cases per kind including boundaries (exactly 2x, zero prev_close,
  missing volume, NULL-padded non-trading days).
- **Pipeline** — one integration test with a recorded Yahoo response asserting that
  a second identical run inserts zero new events (idempotency).
- **Routes** — extend the existing `TestClient` + patched-database pattern in
  `backend/tests/test_routes.py`; add feed pagination and identity-scoping cases.
- **Frontend** — component tests for divider placement (unseen above, seen below)
  and the quiet state. The repo currently has no frontend tests; keep this light.

The existing 40 backend tests must continue to pass.

---

## 15. Risks

| Risk | Mitigation |
| --- | --- |
| Yahoo rate-limits the one-year backfill | Backfill once per symbol, on add, persisted; never re-fetched |
| Vercel function duration on a large refresh | Cap symbols per invocation; pooled fetches; work is resumable because writes are idempotent |
| Cold start — no history means no events | Backfill on first add; detectors run against backfilled bars immediately |
| Empty feed reads as broken, not as calm | The quiet state is designed, not defaulted — it states symbol count and last check time |
| Daily granularity limits scrubber resolution | Accepted and documented; intraday is out of scope |
