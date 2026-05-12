// frontend/lib/api.ts
import { MarketPrice, NewsItem, WatchlistItem } from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  getMarket: () => fetchJSON<MarketPrice[]>("/market"),
  getNews: (category: "trading" | "tech" | "energy") =>
    fetchJSON<NewsItem[]>(`/news?category=${category}`),
  getWatchlist: () => fetchJSON<WatchlistItem[]>("/watchlist"),
  addToWatchlist: (symbol: string, type: "stock" | "crypto" | "forex") =>
    fetchJSON<{ status: string }>("/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, type }),
    }),
  removeFromWatchlist: (symbol: string) =>
    fetchJSON<{ status: string }>(`/watchlist/${symbol}`, { method: "DELETE" }),
};
