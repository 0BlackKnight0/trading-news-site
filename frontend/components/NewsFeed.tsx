"use client";
import { useEffect, useState, useCallback } from "react";
import { NewsItem, NewsCategory } from "@/types";
import { api } from "@/lib/api";
import { useInterval } from "@/hooks/useInterval";
import { NewsCard } from "./NewsCard";

type Category = NewsCategory;

const TABS: {
  key: Category;
  label: string;
  activeClasses: string;
  count?: number;
}[] = [
  {
    key: "trading",
    label: "📈 Trading",
    activeClasses: "bg-[#ff5530] text-white border-[#ff5530]",
  },
  {
    key: "tech",
    label: "🤖 AI & Tech",
    activeClasses: "bg-[#3b82f6] text-white border-[#3b82f6]",
  },
  {
    key: "energy",
    label: "⚡ Energy",
    activeClasses: "bg-[#f97316] text-white border-[#f97316]",
  },
];

interface NewsFeedProps {
  onToggleSidebar: () => void;
}

export function NewsFeed({ onToggleSidebar }: NewsFeedProps) {
  const [activeTab, setActiveTab] = useState<Category>("trading");
  const [news, setNews] = useState<Record<Category, NewsItem[]>>({
    trading: [],
    tech: [],
    energy: [],
  });
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    const [trading, tech, energy] = await Promise.allSettled([
      api.getNews("trading"),
      api.getNews("tech"),
      api.getNews("energy"),
    ]);
    setNews({
      trading: trading.status === "fulfilled" ? trading.value : [],
      tech: tech.status === "fulfilled" ? tech.value : [],
      energy: energy.status === "fulfilled" ? energy.value : [],
    });
    setLastUpdated(new Date());
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);
  useInterval(fetchAll, 300_000);

  const activeNews = news[activeTab];

  return (
    <main className="flex-1 flex flex-col overflow-hidden bg-[#0a0a0a]">
      <div className="px-4 md:px-6 pt-4 md:pt-5 pb-0 border-b border-[#191919]">
        <div className="flex items-center justify-between mb-3 md:mb-4">
          <div className="flex items-center gap-3">
            <button
              onClick={onToggleSidebar}
              className="md:hidden flex flex-col gap-[5px] p-1 -ml-1 text-[#555] hover:text-[#888] transition-colors"
              aria-label="Toggle market sidebar"
            >
              <span className="block w-[18px] h-[1.5px] bg-current rounded-full" />
              <span className="block w-[18px] h-[1.5px] bg-current rounded-full" />
              <span className="block w-[18px] h-[1.5px] bg-current rounded-full" />
            </button>
            <div>
              <h2 className="text-[15px] font-semibold text-white tracking-tight">News Feed</h2>
              <p className="text-[11px] text-[#333] mt-0.5">
                {loading
                  ? "Fetching latest..."
                  : lastUpdated
                  ? `Updated ${lastUpdated.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })} · ${activeNews.length} articles`
                  : ""}
              </p>
            </div>
          </div>
          <button
            onClick={fetchAll}
            className="text-[11px] text-[#444] hover:text-[#888] border border-[#1e1e1e] hover:border-[#2e2e2e] rounded-full px-3 py-1 transition-all shrink-0"
          >
            Refresh
          </button>
        </div>

        <div
          className="flex gap-2 overflow-x-auto pb-0"
          style={{ scrollbarWidth: "none", msOverflowStyle: "none" } as React.CSSProperties}
        >
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`shrink-0 px-4 py-1.5 rounded-full text-[12px] font-semibold border transition-all duration-150 ${
                activeTab === tab.key
                  ? tab.activeClasses
                  : "bg-transparent text-[#555] border-[#1e1e1e] hover:border-[#2e2e2e] hover:text-[#888]"
              }`}
            >
              {tab.label}
              {news[tab.key].length > 0 && (
                <span
                  className={`ml-1.5 text-[10px] ${
                    activeTab === tab.key ? "opacity-70" : "text-[#333]"
                  }`}
                >
                  {news[tab.key].length}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 md:p-6 pt-4 md:pt-5">
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="bg-[#111111] border border-[#1e1e1e] rounded-2xl p-4 animate-pulse"
              >
                <div className="flex justify-between mb-2.5">
                  <div className="h-4 w-16 bg-[#1e1e1e] rounded-full" />
                  <div className="h-4 w-10 bg-[#1e1e1e] rounded" />
                </div>
                <div className="h-4 bg-[#1e1e1e] rounded mb-1.5" />
                <div className="h-4 bg-[#1e1e1e] rounded w-3/4 mb-1.5" />
                <div className="h-3 bg-[#1a1a1a] rounded w-full mt-2" />
                <div className="h-3 bg-[#1a1a1a] rounded w-2/3 mt-1" />
                <div className="h-3 w-20 bg-[#1a1a1a] rounded mt-3" />
              </div>
            ))}
          </div>
        ) : activeNews.length === 0 ? (
          <div className="flex items-center justify-center h-40">
            <p className="text-[#333] text-sm">No articles yet — fetching...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {activeNews.map((item) => (
              <NewsCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
