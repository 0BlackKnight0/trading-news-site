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
      <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 px-2">
        Watchlist
      </div>

      {items.map((item) => (
        <div key={item.id} className="flex items-center justify-between py-1 px-2 group">
          <span className="text-slate-300 text-sm font-mono">{item.symbol}</span>
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-500">{item.type}</span>
            <button
              onClick={() => handleRemove(item.symbol)}
              className="text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity text-xs ml-1"
            >
              ✕
            </button>
          </div>
        </div>
      ))}

      <div className="mt-3 px-2 space-y-2">
        <Input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          placeholder="Add ticker (e.g. RELIANCE)"
          className="h-7 text-xs bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
        />
        <div className="flex gap-1">
          {(["stock", "crypto", "forex"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setType(t)}
              className={`text-xs px-2 py-0.5 rounded transition-colors ${
                type === t ? "bg-indigo-600 text-white" : "bg-slate-700 text-slate-400 hover:bg-slate-600"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <Button
          onClick={handleAdd}
          disabled={loading || !symbol.trim()}
          className="w-full h-7 text-xs bg-indigo-600 hover:bg-indigo-700"
        >
          {loading ? "Adding..." : "Add"}
        </Button>
      </div>
    </div>
  );
}
