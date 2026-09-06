"use client";
import { useCallback, useEffect, useState } from "react";
import { NewsItem } from "@/types";
import { api } from "@/lib/api";
import { useInterval } from "@/hooks/useInterval";

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
      className={`block px-4 py-3 border-b border-border-subtle hover:bg-overlay-hover transition-colors ${
        unseen ? "bg-surface-hover" : ""
      }`}
    >
      <p className={`text-[12.5px] leading-snug ${unseen ? "text-text-primary" : "text-text-secondary"}`}>
        {item.title}
      </p>
      <div className="flex items-center gap-1.5 mt-1.5 text-[10px] text-text-muted">
        {item.symbol && (
          <span className="text-accent font-semibold">{item.symbol}</span>
        )}
        <span>{item.source}</span>
        <span className="ml-auto">{timeAgo(item.published_at)}</span>
      </div>
    </a>
  );
}

// The "Since" changelog for your own watchlist symbols — pulled out as its
// own heading/tab rather than living as the first stack of rows inside the
// generic News tab, so it reads as "your stuff" rather than an afterthought.
export function WatchlistNews() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [lastSeenAt, setLastSeenAt] = useState<string | null>(null);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.getSymbolNews();
      setItems(data.items);
      setUnread(data.unread_count);
      setLastSeenAt(data.news_last_seen_at);
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);
  useInterval(load, 60_000);

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

  return (
    <div>
      <div className="flex items-center gap-2 px-4 pt-4 pb-2">
        <span className="text-[10px] uppercase tracking-[0.12em] text-text-tertiary">
          Watchlist
        </span>
        {unread > 0 && (
          <>
            <span className="text-[10px] text-accent">{unread} new</span>
            <button
              onClick={catchUp}
              className="ml-auto text-[10px] text-text-tertiary hover:text-text-primary border border-border-default rounded-full px-2 py-0.5 transition-colors"
            >
              Mark read
            </button>
          </>
        )}
      </div>

      {loading ? (
        <div className="p-4 space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-12 bg-surface-hover rounded-xl animate-pulse" />
          ))}
        </div>
      ) : failed ? (
        <p className="text-center text-[12px] text-warning py-16">
          Could not reach the news feed. Showing nothing rather than something stale.
        </p>
      ) : items.length === 0 ? (
        <p className="px-4 pb-4 text-[11px] text-text-muted">
          No recent news for your watchlist symbols.
        </p>
      ) : (
        items.map((item) => (
          <Article key={item.id} item={item} unseen={isUnseen(item)} />
        ))
      )}
    </div>
  );
}
