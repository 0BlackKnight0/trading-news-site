"use client";
import { useEffect, useState, useCallback } from "react";
import { MarketPrice, WatchlistItem } from "@/types";
import { api } from "@/lib/api";
import { useInterval } from "@/hooks/useInterval";
import { PriceRow } from "./PriceRow";
import { WatchlistManager } from "./WatchlistManager";

function SectionLabel({ label }: { label: string }) {
  return (
    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mt-4 mb-1 px-2">
      {label}
    </div>
  );
}

export function Sidebar() {
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

  useInterval(fetchMarket, 60_000); // refresh every 60s

  const india = market.filter((m) => m.category === "india");
  const crypto = market.filter((m) => m.category === "crypto").slice(0, 6);
  const forex = market.filter((m) => m.category === "forex");

  return (
    <aside className="w-52 shrink-0 bg-[#13151f] border-r border-slate-800 h-screen overflow-y-auto py-4 flex flex-col">
      <div className="px-2 mb-4">
        <h1 className="text-sm font-bold text-white">Trading Dashboard</h1>
        <p className="text-xs text-slate-500">Live market data</p>
      </div>

      <SectionLabel label="India" />
      {india.map((m) => <PriceRow key={m.symbol} item={m} />)}

      <SectionLabel label="Crypto" />
      {crypto.map((m) => <PriceRow key={m.symbol} item={m} />)}

      <SectionLabel label="Forex" />
      {forex.map((m) => <PriceRow key={m.symbol} item={m} />)}

      <div className="mt-4 border-t border-slate-800 pt-4">
        <WatchlistManager items={watchlist} onUpdate={fetchWatchlist} />
      </div>
    </aside>
  );
}
