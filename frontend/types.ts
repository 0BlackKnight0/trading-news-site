// frontend/types.ts
export interface MarketPrice {
  id: number;
  symbol: string;
  price: number;
  change_pct: number;
  category: "india" | "crypto" | "forex";
}

export interface NewsItem {
  id: number;
  title: string;
  url: string;
  source: string;
  category: "trading" | "tech" | "energy";
  published_at: string | null;
}

export interface WatchlistItem {
  id: number;
  symbol: string;
  type: "stock" | "crypto" | "forex";
  added_at: string;
}

// Derived utility types — use these instead of repeating the unions
export type NewsCategory = NewsItem["category"];     // "trading" | "tech" | "energy"
export type WatchlistType = WatchlistItem["type"];   // "stock" | "crypto" | "forex"
