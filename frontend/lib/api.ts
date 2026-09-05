// frontend/lib/api.ts
import { MarketPrice, NewsItem, WatchlistItem, NewsCategory, WatchlistType, SearchResult, TickerDetail, SymbolNewsResponse } from "@/types";
import { getDeviceKey } from "@/lib/deviceKey";
import { FeedResponse } from "@/types";

// Set NEXT_PUBLIC_API_URL to the deployed API. The localhost fallback is for
// local dev only — if it leaks into a deployment the failure is at least
// obvious, rather than silently pointing at a host that no longer exists.
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { ...(options?.headers ?? {}), "X-Device-Key": getDeviceKey() },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  getMarket: () => fetchJSON<MarketPrice[]>("/market"),
  getNews: (category: NewsCategory) =>
    fetchJSON<NewsItem[]>(`/news?category=${category}`),
  getWatchlist: () => fetchJSON<WatchlistItem[]>("/watchlist"),
  addToWatchlist: (symbol: string, type: WatchlistType) =>
    fetchJSON<{ status: string }>("/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, type }),
    }),
  removeFromWatchlist: (symbol: string) =>
    fetchJSON<{ status: string }>(`/watchlist/${symbol}`, { method: "DELETE" }),
  searchTicker: (q: string) =>
    fetchJSON<SearchResult[]>(`/search?q=${encodeURIComponent(q)}`),
  getTickerDetail: (symbol: string, type: WatchlistType) =>
    fetchJSON<TickerDetail>(`/ticker/${symbol}?type=${type}`),
  getFeed: (cursor?: string) =>
    fetchJSON<FeedResponse>(`/feed${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`),
  markSeen: () =>
    fetchJSON<{ last_seen_at: string }>("/feed/seen", { method: "POST" }),
  getSymbolNews: () => fetchJSON<SymbolNewsResponse>("/news/symbols"),
  markNewsSeen: () =>
    fetchJSON<{ news_last_seen_at: string }>("/news/seen", { method: "POST" }),
};
