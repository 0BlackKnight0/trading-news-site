"use client";
import { useEffect, useState, useCallback } from "react";
import { NewsItem } from "@/types";
import { api } from "@/lib/api";
import { useInterval } from "@/hooks/useInterval";
import { NewsCard } from "./NewsCard";

type Category = "trading" | "tech" | "energy";

const TABS: { key: Category; label: string }[] = [
  { key: "trading", label: "📈 Trading" },
  { key: "tech", label: "🤖 AI & Tech" },
  { key: "energy", label: "⚡ Energy" },
];

export function NewsFeed() {
  const [activeTab, setActiveTab] = useState<Category>("trading");
  const [news, setNews] = useState<Record<Category, NewsItem[]>>({
    trading: [],
    tech: [],
    energy: [],
  });

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
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useInterval(fetchAll, 300_000); // refresh every 5 min

  return (
    <main className="flex-1 p-6 overflow-y-auto">
      <div className="flex gap-2 mb-6">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "bg-indigo-600 text-white"
                : "bg-slate-800 text-slate-400 hover:bg-slate-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {news[activeTab].length === 0 ? (
          <p className="text-slate-500 text-sm col-span-3">Loading news...</p>
        ) : (
          news[activeTab].map((item) => <NewsCard key={item.id} item={item} />)
        )}
      </div>
    </main>
  );
}
