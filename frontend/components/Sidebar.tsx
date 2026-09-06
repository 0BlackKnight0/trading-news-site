"use client";
import { useEffect, useState, useCallback, useMemo } from "react";
import { MarketPrice, WatchlistItem, WatchlistType } from "@/types";
import { api } from "@/lib/api";
import { useInterval } from "@/hooks/useInterval";
import { PriceRow } from "./PriceRow";
import { WatchlistManager } from "./WatchlistManager";

const SECTION_DOTS: Record<string, string> = {
  India: "bg-accent",
  Global: "bg-ai",
  Crypto: "bg-warning",
  Forex: "bg-info",
};

function SectionLabel({ label }: { label: string }) {
  const dot = SECTION_DOTS[label];
  return (
    <div className="flex items-center gap-2 mt-5 mb-1 px-3">
      {dot && <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />}
      <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-text-tertiary">
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

  // Owned here, not inside WatchlistManager: both the watchlist row AND the
  // market row's checkmark need to hide/clear at the same instant a remove
  // is clicked. Keeping this state local to WatchlistManager left the
  // checkmark depending solely on fetchWatchlist's round trip, so on real
  // network latency (unlike localhost) the row could vanish instantly while
  // the checkmark visibly lagged behind for a second or more.
  const [pendingRemovals, setPendingRemovals] = useState<Set<string>>(new Set());

  const fetchWatchlist = useCallback(async () => {
    // Called right after an add/remove, back-to-back with the mutation's own
    // request — a transient failure here (seen live: net::ERR_FAILED on the
    // immediate follow-up GET) previously had no recovery path, leaving the
    // watchlist showing pre-change state until something else, like a full
    // page reload, happened to trigger a working fetch. One retry absorbs
    // that class of one-off failure without a full retry framework.
    let data: WatchlistItem[] | null = null;
    try {
      data = await api.getWatchlist();
    } catch (e) {
      console.error("watchlist fetch failed, retrying once", e);
      try {
        data = await api.getWatchlist();
      } catch (e2) {
        console.error(e2);
      }
    }
    if (!data) return;
    setWatchlist(data);
    // A pending removal is only "done" once the server-confirmed list no
    // longer contains it — this also makes re-adding the same symbol later
    // show up correctly rather than staying hidden.
    const present = new Set(data.map((w) => w.symbol));
    setPendingRemovals((prev) => {
      const next = new Set([...prev].filter((sym) => present.has(sym)));
      return next.size === prev.size ? prev : next;
    });
  }, []);

  useEffect(() => {
    fetchMarket();
    fetchWatchlist();
  }, [fetchMarket, fetchWatchlist]);

  useInterval(fetchMarket, 60_000);

  const visibleWatchlist = useMemo(
    () => watchlist.filter((w) => !pendingRemovals.has(w.symbol)),
    [watchlist, pendingRemovals]
  );

  // Matched against a market row's watchlist_symbol (the real Yahoo
  // ticker), not its display symbol — "NIFTY" is never what actually ends
  // up in the watchlist table, "^NSEI" is. Derived from visibleWatchlist,
  // not raw watchlist, so a checkmark clears in the same instant its
  // watchlist row disappears.
  const watchedSymbols = useMemo(
    () => new Set(visibleWatchlist.map((w) => w.symbol)),
    [visibleWatchlist]
  );

  async function handleAddFromMarket(symbol: string, type: WatchlistType) {
    await api.addToWatchlist(symbol, type);
    await fetchWatchlist();
  }

  function handleRemoveStart(symbol: string) {
    setPendingRemovals((prev) => new Set(prev).add(symbol));
  }

  function handleRemoveFailed(symbol: string) {
    // The delete didn't actually happen — put it back rather than leaving
    // it looking removed when it isn't.
    setPendingRemovals((prev) => {
      const next = new Set(prev);
      next.delete(symbol);
      return next;
    });
  }

  const india = market.filter((m) => m.category === "india");
  const global_ = market.filter((m) => m.category === "global");
  const crypto = market.filter((m) => m.category === "crypto").slice(0, 6);
  const forex = market.filter((m) => m.category === "forex");

  return (
    <aside className={`
      fixed inset-y-0 left-0 z-40 md:relative md:z-auto md:inset-auto
      w-[260px] md:w-[220px] shrink-0
      bg-surface border-r border-border-default
      h-screen overflow-hidden flex flex-col
      transition-transform duration-300 ease-in-out
      ${isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
    `}>
      <div className="px-3 pt-5 pb-3 border-b border-border-default">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 bg-positive rounded-full animate-pulse" />
          </div>
          <button
            onClick={onClose}
            className="md:hidden text-text-muted hover:text-text-tertiary p-1 -mr-1 transition-colors"
            aria-label="Close sidebar"
          >
            ✕
          </button>
        </div>
        {/* The client polls every 60s, but the server serves a cache with a
            15-minute TTL — and on Hobby the cron runs once a day. Claiming
            "Live" was the exact dishonesty this rebuild set out to remove;
            each row states its own age instead. */}
        <p className="text-[10px] text-text-tertiary mt-0.5 ml-3.5">Delayed · cached up to 15 min</p>
      </div>

      <div className="flex-1 overflow-y-auto py-2 overscroll-contain">
        {india.length > 0 && (
          <>
            <SectionLabel label="India" />
            {india.map((m) => (
              <PriceRow
                key={m.symbol}
                item={m}
                alreadyWatched={!!m.watchlist_symbol && watchedSymbols.has(m.watchlist_symbol)}
                onAdd={handleAddFromMarket}
              />
            ))}
          </>
        )}

        {global_.length > 0 && (
          <>
            <SectionLabel label="Global" />
            {global_.map((m) => (
              <PriceRow
                key={m.symbol}
                item={m}
                alreadyWatched={!!m.watchlist_symbol && watchedSymbols.has(m.watchlist_symbol)}
                onAdd={handleAddFromMarket}
              />
            ))}
          </>
        )}

        {crypto.length > 0 && (
          <>
            <SectionLabel label="Crypto" />
            {crypto.map((m) => (
              <PriceRow
                key={m.symbol}
                item={m}
                alreadyWatched={!!m.watchlist_symbol && watchedSymbols.has(m.watchlist_symbol)}
                onAdd={handleAddFromMarket}
              />
            ))}
          </>
        )}

        {forex.length > 0 && (
          <>
            <SectionLabel label="Forex" />
            {forex.map((m) => (
              <PriceRow
                key={m.symbol}
                item={m}
                alreadyWatched={!!m.watchlist_symbol && watchedSymbols.has(m.watchlist_symbol)}
                onAdd={handleAddFromMarket}
              />
            ))}
          </>
        )}

        <div className="mt-4 border-t border-border-default pt-3">
          <WatchlistManager
            items={visibleWatchlist}
            onUpdate={fetchWatchlist}
            onRemoveStart={handleRemoveStart}
            onRemoveFailed={handleRemoveFailed}
          />
        </div>
      </div>
    </aside>
  );
}
