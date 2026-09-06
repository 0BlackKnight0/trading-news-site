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
  { key: "markets", label: "Markets", color: "var(--accent)" },
  { key: "commodities", label: "Gold & Oil", color: "var(--commodity)" },
  { key: "ai", label: "AI", color: "var(--ai)" },
  { key: "energy", label: "EV & Energy", color: "var(--positive)" },
  { key: "crypto", label: "Crypto", color: "var(--warning)" },
  { key: "geopolitics", label: "Politics", color: "var(--info)" },
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
      className="group flex flex-col bg-surface border border-border-default border-l-[3px] rounded-2xl p-4 hover:border-border-strong hover:bg-surface-hover transition-colors"
    >
      <div className="flex items-center gap-1.5 mb-2">
        <span
          className="text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
          style={{ color, backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)` }}
        >
          {label}
        </span>
        {item.symbol && (
          <span className="text-[10px] text-text-tertiary font-medium">{item.symbol}</span>
        )}
      </div>

      <p className="text-[13px] font-medium leading-snug text-text-secondary group-hover:text-text-primary transition-colors line-clamp-3">
        {item.title}
      </p>

      {item.summary && (
        <p className="text-[11px] text-text-muted mt-1.5 leading-relaxed line-clamp-2">
          {item.summary}
        </p>
      )}

      <div className="flex items-center gap-1.5 mt-3 pt-3 border-t border-border-subtle text-[10px] text-text-muted">
        <span className="font-medium text-text-tertiary">{item.source}</span>
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
        <span className="text-[10px] uppercase tracking-[0.12em] text-text-tertiary">
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
                  : "text-[10px] px-2.5 py-1 rounded-full border font-medium transition-colors bg-transparent text-text-tertiary border-border-default hover:text-text-secondary"
              }
              style={
                active
                  ? { color: c.color, backgroundColor: `color-mix(in srgb, ${c.color} 12%, transparent)`, borderColor: `color-mix(in srgb, ${c.color} 40%, transparent)` }
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
            <div key={i} className="h-32 bg-surface-hover rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : failed ? (
        <p className="text-center text-[12px] text-warning py-16">
          Could not reach the news feed. Showing nothing rather than something stale.
        </p>
      ) : items.length === 0 ? (
        <p className="text-[11px] text-text-muted py-4">Nothing here yet.</p>
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
