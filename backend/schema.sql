-- backend/schema.sql
-- Run this in the Supabase SQL editor at supabase.com.
-- Safe to re-run: every statement is idempotent.
CREATE TABLE IF NOT EXISTS market_cache (
  id SERIAL PRIMARY KEY,
  symbol TEXT UNIQUE NOT NULL,
  price NUMERIC,
  change_pct NUMERIC,
  category TEXT,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS news_cache (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  url TEXT,
  source TEXT,
  category TEXT,
  published_at TIMESTAMPTZ,
  fetched_at TIMESTAMPTZ DEFAULT now()
);

-- Article summaries, added after the initial schema.
ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS summary TEXT;

CREATE TABLE IF NOT EXISTS watchlist (
  id SERIAL PRIMARY KEY,
  symbol TEXT UNIQUE NOT NULL,
  type TEXT,
  added_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS telegram_users (
  id SERIAL PRIMARY KEY,
  chat_id BIGINT UNIQUE NOT NULL,
  registered_at TIMESTAMPTZ DEFAULT now()
);

-- Tracks when each cache was last refreshed. On serverless there is no
-- background loop, so reads consult this to decide whether to refresh.
CREATE TABLE IF NOT EXISTS refresh_meta (
  key TEXT PRIMARY KEY,
  updated_at TIMESTAMPTZ DEFAULT now()
);

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

-- ===== Improved news feed =====

-- Symbol news rows carry `symbol` and leave `category` NULL. Category news
-- rows are the reverse. That is what keeps get_news and get_symbol_news from
-- returning each other's rows.
ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS symbol TEXT;
ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS score  INT NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS news_cache_symbol_idx
  ON news_cache (symbol, published_at DESC);
CREATE INDEX IF NOT EXISTS news_cache_ranked_idx
  ON news_cache (category, score DESC, published_at DESC);

-- News and Changes track "since you last looked" separately: catching up on
-- news must not silently mark a RANGE_BREAK as read.
ALTER TABLE user_state
  ADD COLUMN IF NOT EXISTS news_last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Retention. Repeated by prune_news() on every refresh; this seeds it.
DELETE FROM news_cache WHERE published_at < now() - INTERVAL '30 days';

-- Company name per symbol, used to match news articles to watchlist symbols.
-- Articles say "Infosys", not "INFY.NS".
ALTER TABLE symbol_stats ADD COLUMN IF NOT EXISTS name TEXT;
