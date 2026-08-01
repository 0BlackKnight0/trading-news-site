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
