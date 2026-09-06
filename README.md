# Since — a Smart Market Watchlist

**Since** answers one question: *what changed with the things I'm watching, since the last time I looked?*

Most watchlists are scoreboards — every row, always visible, equally weighted, forcing you to re-scan the whole board every time to spot what's different. Since keeps a **changelog** instead: an append-only event log with a single divider marking where you stopped reading, plus a per-symbol time scrubber to replay how a move actually unfolded.

Built for the CODE 2026 "Build a Smart Market Watchlist" brief.

---

## What it does

- **Watchlist** — add stocks, indices, crypto, or forex pairs; prices are cached and labeled with their real age, never claimed "live" when they're 15 minutes old.
- **Changes ("The Line")** — a feed of only the events that crossed a threshold since your last visit: big moves, volume spikes, new 52-week highs/lows, and opening gaps. Absence of a row is a decision, not a gap.
- **Rewind** — click into any watched symbol to scrub its own chart from your last visit to now, day by day, with a play button that replays the move.
- **News** — a "Your Symbols" feed matched to what you're actually watching, plus a general "Market Intelligence" feed with category filters (Markets, Gold & Oil, AI, EV & Energy, Crypto, Politics).
- **Light/dark theme**, no account required (a device key in `localStorage` identifies you — see [Design notes](#design-notes)).

## Why it's built this way

- **"Meaningful change" is defined relative to each symbol's own behavior**, not a flat percentage — a 2% move means something different for a bank stock than a mid-cap coin. See `backend/signals/detect.py`.
- **No background workers.** This runs on Vercel's free Hobby tier, which gives you serverless functions and one cron run *per day* — nothing else. Every read checks if its cache is stale and refreshes inline instead of relying on a scheduler. See [`DEPLOYMENT.md`](DEPLOYMENT.md#how-refresh-works-and-why) for the full reasoning.
- **Every price states its own age.** Nothing claims "live" when it isn't — staleness is surfaced, not hidden.
- **News matching is "never wrong, sometimes sparse."** Headlines are matched to your watched symbols by name/alias with word-boundary anchoring and a denylist for ordinary-English-word tickers (e.g. bare "gold" or "target"), so coverage is real but incomplete rather than fabricated.

Full design rationale, the phases considered, and what was deliberately deferred: [`docs/superpowers/specs/2026-09-05-smart-watchlist-design.md`](docs/superpowers/specs/2026-09-05-smart-watchlist-design.md).

---

## Architecture

```
Next.js 16 frontend  ──HTTP──>  FastAPI backend  ──>  Supabase (Postgres)
   (Vercel)                       (Vercel, serverless)      │
                                        │                    │
                                        └──> Yahoo Finance / RSS / NewsAPI
```

Two separate Vercel projects from one repo (`frontend/` and `backend/` are each their own deployment root — Vercel needs one project per root directory). No persistent server anywhere; each request is a stateless function invocation, and Supabase is the only thing that survives between them.

**Identity** is a random key generated client-side and sent as `X-Device-Key` — not real authentication, but enough to give each visitor their own private watchlist instead of one shared global list.

---

## Project structure

```
backend/
  routes/          One file per API surface (market, news, watchlist, feed, history, ...)
  aggregator/       Market + news fetching, symbol/headline matching (pure functions)
  signals/          The event detectors — pure, no I/O, table-driven-testable
  pipeline.py       Fetch → snapshot → stats → detect → events, per symbol
  aggregator_loop.py  On-read cache revalidation (no scheduler needed)
  database.py       All Supabase queries live here
  tests/            248 tests, pytest
  schema.sql        Full DB schema — idempotent, safe to re-run

frontend/
  app/              Next.js App Router entry point + global styles/theme tokens
  components/       One component per UI concern (Sidebar, Feed, TickerModal, RewindScrubber, ...)
  lib/api.ts        The one place that talks to the backend

docs/superpowers/
  specs/            Design documents (the "why")
  plans/            Implementation plans (the "how", task-by-task)
```

---

## Running it locally

**Prerequisites:** Python 3.11+, Node 18+, a free [Supabase](https://supabase.com) project.

### 1. Database

Open your Supabase project's SQL editor and run [`backend/schema.sql`](backend/schema.sql) once. It's idempotent — safe to re-run if you're ever unsure it applied.

### 2. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` — at minimum `SUPABASE_URL`, `SUPABASE_KEY`, and `CRON_SECRET` (any random 16+ character string). `NEWSAPI_KEY` and `TELEGRAM_BOT_TOKEN` are optional; the app degrades gracefully without them (RSS feeds still work, the Telegram digest just doesn't send).

```bash
uvicorn main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/health` → `{"status":"ok"}`

### 3. Frontend

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Open `http://localhost:3000`. First load will be sparse — the watchlist and event log are empty until you add a symbol (search box in the sidebar), and price history backfills in the background after that.

### Run the tests

```bash
cd backend
pytest              # 248 tests, no network or Supabase access needed — everything is mocked
```

The frontend has no automated test suite; changes are verified manually against a running instance (see the design docs' testing sections for why this was an intentional scope decision).

---

## Deploying

Full step-by-step Vercel setup (two separate projects, environment variables, the Telegram webhook, and *why* the refresh model looks the way it does on a serverless free tier) is in [`DEPLOYMENT.md`](DEPLOYMENT.md).

---

## API surface (backend)

| Route | Purpose |
| --- | --- |
| `GET /market` | Cached prices for the fixed India/Global/Crypto/Forex board |
| `GET /watchlist` `POST` `DELETE /{symbol}` | Per-user watchlist, backfills history on add |
| `GET /feed` `POST /feed/seen` | The event changelog + "catch up" divider |
| `GET /history?symbol=` | One symbol's price series, for the Rewind scrubber |
| `GET /news?category=` `GET /news/symbols` `POST /news/seen` | General + per-watchlist news |
| `GET /search?q=&type=` | Ticker autocomplete |
| `GET /ticker/{symbol}` | Full detail view for the ticker modal |
| `GET /cron/daily` | Daily refresh + Telegram digest (Vercel Cron only, needs `CRON_SECRET`) |
| `POST /admin/refresh` | Manual refresh, needs `CRON_SECRET` |
| `POST /telegram/webhook` | Telegram bot updates |

Every route except `/health` and `/cron/daily`/`/admin/refresh` (which use `CRON_SECRET` instead) requires `X-Device-Key`.

---

## Known limits (honestly, not defensively)

- **Phase 1 ("The Line" + priced watchlist) and the Rewind scrubber are built and live.** A third phase — Telegram digest wired to the same event feed, pin/mute per symbol, cross-device sync codes — was scoped but not built; see the design spec's §12–13 for why and what it would take.
- **News coverage is intentionally uneven.** A handful of index/crypto/forex symbols have hand-reviewed aliases; most individual equities match on company name alone, which is real but not exhaustive coverage.
- **Free-tier cadence.** Prices and news refresh on-read (every 15 minutes of active use) rather than continuously; the daily digest runs once, at a Vercel-scheduled time within roughly an hour of 08:00 IST, not on the dot.
