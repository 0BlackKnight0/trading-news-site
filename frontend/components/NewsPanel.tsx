"use client";
import { useCallback, useEffect, useState } from "react";
import { NewsCategory, NewsItem } from "@/types";
import { api } from "@/lib/api";
import { useInterval } from "@/hooks/useInterval";

const CATEGORIES: { key: NewsCategory; label: string }[] = [
  { key: "trading", label: "Trading" },
  { key: "tech", label: "AI & Tech" },
  { key: "energy", label: "Energy" },
];

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function Article({ item, unseen }: { item: NewsItem; unseen: boolean }) {
  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className={`block px-4 py-3 border-b border-[#151515] hover:bg-white/[0.02] transition-colors ${
        unseen ? "bg-[#0e0e0e]" : ""
      }`}
    >
      <p className={`text-[12.5px] leading-snug ${unseen ? "text-white" : "text-[#8a8a8a]"}`}>
        {item.title}
      </p>
      <div className="flex items-center gap-1.5 mt-1.5 text-[10px] text-[#4a4a4a]">
        {item.symbol && (
          <span className="text-[#ff5530] font-semibold">{item.symbol}</span>
        )}
        <span>{item.source}</span>
        <span className="ml-auto">{timeAgo(item.published_at)}</span>
      </div>
    </a>
  );
}

export function NewsPanel() {
  const [symbolNews, setSymbolNews] = useState<NewsItem[]>([]);
  const [lastSeenAt, setLastSeenAt] = useState<string | null>(null);
  const [unread, setUnread] = useState(0);
  const [category, setCategory] = useState<NewsCategory>("trading");
  const [marketNews, setMarketNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    const [symbols, markets] = await Promise.allSettled([
      api.getSymbolNews(),
      api.getNews(category),
    ]);
    if (symbols.status === "fulfilled") {
      setSymbolNews(symbols.value.items);
      setUnread(symbols.value.unread_count);
      setLastSeenAt(symbols.value.news_last_seen_at);
    }
    setMarketNews(markets.status === "fulfilled" ? markets.value : []);
    setFailed(symbols.status === "rejected" && markets.status === "rejected");
    setLoading(false);
  }, [category]);

  useEffect(() => {
    load();
  }, [load]);
  useInterval(load, 300_000);

  async function catchUp() {
    try {
      const { news_last_seen_at } = await api.markNewsSeen();
      setLastSeenAt(news_last_seen_at);
      setUnread(0);
    } catch {
      setFailed(true);
    }
  }

  const isUnseen = (item: NewsItem) =>
    lastSeenAt !== null && (item.published_at ?? "") > lastSeenAt;

  if (loading) {
    return (
      <div className="p-4 space-y-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-12 bg-[#111] rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (failed) {
    return (
      <p className="text-center text-[12px] text-[#f59e0b] py-16">
        Could not reach the news feed. Showing nothing rather than something stale.
      </p>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-2 px-4 pt-4 pb-2">
        <span className="text-[10px] uppercase tracking-[0.12em] text-[#555]">
          Your symbols
        </span>
        {unread > 0 && (
          <>
            <span className="text-[10px] text-[#ff5530]">{unread} new</span>
            <button
              onClick={catchUp}
              className="ml-auto text-[10px] text-[#777] hover:text-white border border-[#1e1e1e] rounded-full px-2 py-0.5 transition-colors"
            >
              Mark read
            </button>
          </>
        )}
      </div>

      {symbolNews.length === 0 ? (
        <p className="px-4 pb-4 text-[11px] text-[#3a3a3a]">
          No recent news for your watchlist symbols.
        </p>
      ) : (
        symbolNews.map((item) => (
          <Article key={item.id} item={item} unseen={isUnseen(item)} />
        ))
      )}

      <div className="flex items-center gap-2 px-4 pt-6 pb-2">
        <span className="text-[10px] uppercase tracking-[0.12em] text-[#555]">
          Markets
        </span>
        <div className="flex gap-1.5 ml-3">
          {CATEGORIES.map((c) => (
            <button
              key={c.key}
              onClick={() => setCategory(c.key)}
              className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
                category === c.key
                  ? "bg-white text-black border-white font-semibold"
                  : "bg-transparent text-[#555] border-[#1e1e1e] hover:text-[#888]"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      {marketNews.length === 0 ? (
        <p className="px-4 pb-4 text-[11px] text-[#3a3a3a]">Nothing here yet.</p>
      ) : (
        marketNews.map((item) => (
          <Article key={item.id} item={item} unseen={false} />
        ))
      )}
    </div>
  );
}
