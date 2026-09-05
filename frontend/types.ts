// frontend/types.ts
export interface MarketPrice {
  id: number;
  symbol: string;
  price: number;
  change_pct: number;
  category: "india" | "crypto" | "forex" | "global";
}

export interface NewsItem {
  id: number;
  title: string;
  url: string;
  source: string;
  category: "trading" | "tech" | "energy";
  published_at: string | null;
  summary?: string | null;
}

export interface WatchlistItem {
  id: number;
  symbol: string;
  type: "stock" | "crypto" | "forex";
  added_at: string;
  price: number | null;
  change_pct: number | null;
  as_of: string | null;
}

// Derived utility types — use these instead of repeating the unions
export type NewsCategory = NewsItem["category"];     // "trading" | "tech" | "energy"
export type WatchlistType = WatchlistItem["type"];   // "stock" | "crypto" | "forex"

export interface SearchResult {
  symbol: string;
  name: string;
  exchange: string;
  type: WatchlistType;
}

export interface TickerNews {
  title: string;
  url: string;
  source: string;
  published_at: string;
  summary: string;
}

export interface TickerDetail {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  change_abs: number;
  currency: string;
  market_cap: number | null;
  volume: number | null;
  pe_ratio: number | null;
  week_52_high: number | null;
  week_52_low: number | null;
  open: number | null;
  prev_close: number | null;
  news: TickerNews[];
  error?: string;
}

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
