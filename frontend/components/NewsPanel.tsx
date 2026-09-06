"use client";
import { useCallback, useEffect, useState } from "react";
import { NewsCategory, NewsItem } from "@/types";
import { api } from "@/lib/api";
import { useInterval } from "@/hooks/useInterval";

// One accent per category, reused from colors already established elsewhere
// in the app (orange = the primary brand accent, amber = crypto, blue =
// forex/info) rather than inventing a new palette — a category still needs
// to be tellable apart at a glance, but the app should read as one product.
const CATEGORIES: { key: NewsCategory; label: string; color: string }[] = [
  { key: "markets", label: "Markets", color: "#ff5530" },
  { key: "commodities", label: "Gold & Oil", color: "#d4a054" },
  { key: "ai", label: "AI", color: "#5eb3b3" },
  { key: "energy", label: "EV & Energy", color: "#22c55e" },
  { key: "crypto", label: "Crypto", color: "#f59e0b" },
  { key: "geopolitics", label: "Politics", color: "#3b82f6" },
];

function categoryMeta(key: NewsCategory | null) {
  return CATEGORIES.find((c) => c.key === key) ?? CATEGORIES[0];
}

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function NewsCard({ item }: { item: NewsItem }) {
  const { label, color } = categoryMeta(item.category);
  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      style={{ borderLeftColor: color }}
      className="group flex flex-col bg-[#101010] border border-[#1c1c1c] border-l-[3px] rounded-2xl p-4 hover:border-[#2a2a2a] hover:bg-[#131313] transition-colors"
    >
      <div className="flex items-center gap-1.5 mb-2">
        <span
          className="text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
          style={{ color, backgroundColor: `${color}1a` }}
        >
          {label}
        </span>
        {item.symbol && (
          <span className="text-[10px] text-[#666] font-medium">{item.symbol}</span>
        )}
      </div>

      <p className="text-[13px] font-medium leading-snug text-[#d8d8d8] group-hover:text-white transition-colors line-clamp-3">
        {item.title}
      </p>

      {item.summary && (
        <p className="text-[11px] text-[#5c5c5c] mt-1.5 leading-relaxed line-clamp-2">
          {item.summary}
        </p>
      )}

      <div className="flex items-center gap-1.5 mt-3 pt-3 border-t border-[#181818] text-[10px] text-[#4a4a4a]">
        <span className="font-medium text-[#666]">{item.source}</span>
        <span className="ml-auto">{timeAgo(item.published_at)}</span>
      </div>
    </a>
  );
}

export function NewsPanel() {
  const [category, setCategory] = useState<NewsCategory>("markets");
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.getNews(category);
      setItems(data);
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);
  // The API revalidates its source cache every fifteen minutes. Polling more
  // often keeps an active page responsive without repeatedly fetching feeds.
  useInterval(load, 60_000);

  return (
    <div className="p-4">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-[10px] uppercase tracking-[0.12em] text-[#555]">
          Market intelligence
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5 mb-4">
        {CATEGORIES.map((c) => {
          const active = category === c.key;
          return (
            <button
              key={c.key}
              onClick={() => setCategory(c.key)}
              className={
                active
                  ? "text-[10px] px-2.5 py-1 rounded-full border font-semibold transition-colors"
                  : "text-[10px] px-2.5 py-1 rounded-full border font-medium transition-colors bg-transparent text-[#555] border-[#1e1e1e] hover:text-[#888]"
              }
              style={
                active
                  ? { color: c.color, backgroundColor: `${c.color}1a`, borderColor: `${c.color}66` }
                  : undefined
              }
            >
              {c.label}
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-32 bg-[#111] rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : failed ? (
        <p className="text-center text-[12px] text-[#f59e0b] py-16">
          Could not reach the news feed. Showing nothing rather than something stale.
        </p>
      ) : items.length === 0 ? (
        <p className="text-[11px] text-[#3a3a3a] py-4">Nothing here yet.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
          {items.map((item) => (
            <NewsCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
