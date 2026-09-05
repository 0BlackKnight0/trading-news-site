"use client";
import { useEffect, useState, useCallback } from "react";
import { MarketPrice, WatchlistItem } from "@/types";
import { api } from "@/lib/api";
import { useInterval } from "@/hooks/useInterval";
import { PriceRow } from "./PriceRow";
import { WatchlistManager } from "./WatchlistManager";

const SECTION_DOTS: Record<string, string> = {
  India: "bg-[#ff5530]",
  Global: "bg-[#a855f7]",
  Crypto: "bg-[#f59e0b]",
  Forex: "bg-[#3b82f6]",
};

function SectionLabel({ label }: { label: string }) {
  const dot = SECTION_DOTS[label];
  return (
    <div className="flex items-center gap-2 mt-5 mb-1 px-3">
      {dot && <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />}
      <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[#555]">
        {label}
      </span>
    </div>
  );
}

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const [market, setMarket] = useState<MarketPrice[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);

  const fetchMarket = useCallback(async () => {
    try {
      const data = await api.getMarket();
      setMarket(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchWatchlist = useCallback(async () => {
    try {
      const data = await api.getWatchlist();
      setWatchlist(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    fetchMarket();
    fetchWatchlist();
  }, [fetchMarket, fetchWatchlist]);

  useInterval(fetchMarket, 60_000);

  const india = market.filter((m) => m.category === "india");
  const global_ = market.filter((m) => m.category === "global");
  const crypto = market.filter((m) => m.category === "crypto").slice(0, 6);
  const forex = market.filter((m) => m.category === "forex");

  return (
    <aside className={`
      fixed inset-y-0 left-0 z-40 md:relative md:z-auto md:inset-auto
      w-[260px] md:w-[220px] shrink-0
      bg-[#0d0d0d] border-r border-[#1c1c1c]
      h-screen overflow-hidden flex flex-col
      transition-transform duration-300 ease-in-out
      ${isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
    `}>
      <div className="px-3 pt-5 pb-3 border-b border-[#1c1c1c]">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 bg-[#22c55e] rounded-full animate-pulse" />
            <h1 className="text-[13px] font-semibold text-white tracking-tight">Market Intelligence</h1>
          </div>
          <button
            onClick={onClose}
            className="md:hidden text-[#444] hover:text-[#777] p-1 -mr-1 transition-colors"
            aria-label="Close sidebar"
          >
            ✕
          </button>
        </div>
        {/* The client polls every 60s, but the server serves a cache with a
            15-minute TTL — and on Hobby the cron runs once a day. Claiming
            "Live" was the exact dishonesty this rebuild set out to remove;
            each row states its own age instead. */}
        <p className="text-[10px] text-[#555] mt-0.5 ml-3.5">Delayed · cached up to 15 min</p>
      </div>

      <div className="flex-1 overflow-y-auto py-2 overscroll-contain">
        {india.length > 0 && (
          <>
            <SectionLabel label="India" />
            {india.map((m) => <PriceRow key={m.symbol} item={m} />)}
          </>
        )}

        {global_.length > 0 && (
          <>
            <SectionLabel label="Global" />
            {global_.map((m) => <PriceRow key={m.symbol} item={m} />)}
          </>
        )}

        {crypto.length > 0 && (
          <>
            <SectionLabel label="Crypto" />
            {crypto.map((m) => <PriceRow key={m.symbol} item={m} />)}
          </>
        )}

        {forex.length > 0 && (
          <>
            <SectionLabel label="Forex" />
            {forex.map((m) => <PriceRow key={m.symbol} item={m} />)}
          </>
        )}

        <div className="mt-4 border-t border-[#1c1c1c] pt-3">
          <WatchlistManager items={watchlist} onUpdate={fetchWatchlist} />
        </div>
      </div>
    </aside>
  );
}
