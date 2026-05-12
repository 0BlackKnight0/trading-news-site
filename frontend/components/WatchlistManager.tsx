"use client";
import { useState } from "react";
import { WatchlistItem, WatchlistType } from "@/types";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Props {
  items: WatchlistItem[];
  onUpdate: () => void;
}

export function WatchlistManager({ items, onUpdate }: Props) {
  const [symbol, setSymbol] = useState("");
  const [type, setType] = useState<WatchlistType>("stock");
  const [loading, setLoading] = useState(false);

  async function handleAdd() {
    if (!symbol.trim()) return;
    setLoading(true);
    try {
      await api.addToWatchlist(symbol.trim().toUpperCase(), type);
      setSymbol("");
      onUpdate();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleRemove(sym: string) {
    try {
      await api.removeFromWatchlist(sym);
      onUpdate();
    } catch (e) {
      console.error(e);
    }
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-2 px-3">
        <div className="w-1.5 h-1.5 rounded-full bg-[#22c55e] shrink-0" />
        <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[#3a3a3a]">
          Watchlist
        </span>
      </div>

      {items.map((item) => (
        <div key={item.id} className="flex items-center justify-between py-1.5 px-3 group hover:bg-white/[0.02]">
          <span className="text-[11px] font-medium text-[#888]">{item.symbol}</span>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#333]">{item.type}</span>
            <button
              onClick={() => handleRemove(item.symbol)}
              className="text-[#2a2a2a] hover:text-[#ef4444] opacity-0 group-hover:opacity-100 transition-all text-[10px] ml-0.5"
            >
              ✕
            </button>
          </div>
        </div>
      ))}

      <div className="mt-3 px-3 space-y-2">
        <Input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          placeholder="Add ticker (e.g. RELIANCE)"
          className="h-7 text-[11px] bg-[#161616] border-[#2a2a2a] text-[#aaa] placeholder:text-[#333] rounded-lg"
        />
        <div className="flex gap-1">
          {(["stock", "crypto", "forex"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setType(t)}
              className={`text-[10px] px-2 py-0.5 rounded-full transition-colors ${
                type === t
                  ? "bg-white text-black font-semibold"
                  : "bg-[#1a1a1a] text-[#555] hover:text-[#888] border border-[#2a2a2a]"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <Button
          onClick={handleAdd}
          disabled={loading || !symbol.trim()}
          className="w-full h-7 text-[11px] bg-white text-black hover:bg-[#e0e0e0] rounded-full font-semibold"
        >
          {loading ? "Adding..." : "Add"}
        </Button>
      </div>
    </div>
  );
}
