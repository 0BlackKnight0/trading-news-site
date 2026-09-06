"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useInterval } from "@/hooks/useInterval";
import { Feed } from "./Feed";
import { NewsPanel } from "./NewsPanel";
import { WatchlistNews } from "./WatchlistNews";
import { ThemeToggle } from "./ThemeToggle";

type Tab = "watchlist" | "news" | "changes";

export function MainPanel({ onToggleSidebar }: { onToggleSidebar: () => void }) {
  const [tab, setTab] = useState<Tab>("news");
  const [changesUnread, setChangesUnread] = useState(0);
  const [watchlistUnread, setWatchlistUnread] = useState(0);

  // Both badges have to stay live regardless of which tab is open, otherwise
  // a firing detector or a fresh symbol article is invisible until the user
  // happens to switch tabs.
  useEffect(() => {
    api.getFeed().then((d) => setChangesUnread(d.unread_count)).catch(() => {});
    api.getSymbolNews().then((d) => setWatchlistUnread(d.unread_count)).catch(() => {});
  }, [tab]);
  useInterval(() => {
    api.getFeed().then((d) => setChangesUnread(d.unread_count)).catch(() => {});
    api.getSymbolNews().then((d) => setWatchlistUnread(d.unread_count)).catch(() => {});
  }, 120_000);

  const TABS: { key: Tab; label: string; unread: number }[] = [
    { key: "watchlist", label: "watchlist", unread: watchlistUnread },
    { key: "news", label: "news", unread: 0 },
    { key: "changes", label: "changes", unread: changesUnread },
  ];

  return (
    <main className="flex-1 flex flex-col overflow-hidden bg-app">
      <header className="px-4 md:px-6 py-4 border-b border-border-subtle flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="md:hidden flex flex-col gap-[5px] p-1 -ml-1 text-text-tertiary hover:text-text-secondary transition-colors"
          aria-label="Toggle market sidebar"
        >
          <span className="block w-[18px] h-[1.5px] bg-current rounded-full" />
          <span className="block w-[18px] h-[1.5px] bg-current rounded-full" />
          <span className="block w-[18px] h-[1.5px] bg-current rounded-full" />
        </button>
        <nav className="flex gap-1" role="tablist">
          {TABS.map(({ key, label, unread }) => (
            <button
              key={key}
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
              className={`text-[12px] px-3 py-1 rounded-full transition-colors capitalize ${
                tab === key
                  ? "bg-text-primary/10 text-text-primary font-semibold"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
            >
              {label}
              {unread > 0 && (
                <span className="ml-1.5 text-[10px] text-accent">{unread}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        {tab === "watchlist" ? <WatchlistNews /> : tab === "news" ? <NewsPanel /> : <Feed embedded />}
      </div>
    </main>
  );
}
