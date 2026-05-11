-- backend/schema.sql
-- Run this once in Supabase SQL editor at supabase.com
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
