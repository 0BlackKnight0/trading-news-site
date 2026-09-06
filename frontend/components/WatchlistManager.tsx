"use client";
import { useState, useRef, useEffect } from "react";
import { WatchlistItem, WatchlistType, SearchResult } from "@/types";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { TickerModal } from "./TickerModal";

interface Props {
  items: WatchlistItem[];
  onUpdate: () => void;
  // Called synchronously, before the DELETE request, so the parent can hide
  // this symbol's watchlist row and clear its market-row checkmark at the
  // same instant — not one after the other as the delete's own round trip
  // happens to resolve.
  onRemoveStart: (symbol: string) => void;
  onRemoveFailed: (symbol: string) => void;
}

function ageLabel(asOf: string | null): string {
  if (!asOf) return "no data yet";
  const minutes = Math.floor((Date.now() - new Date(asOf).getTime()) / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function WatchlistManager({ items, onUpdate, onRemoveStart, onRemoveFailed }: Props) {
  const [symbol, setSymbol] = useState("");
  const [type, setType] = useState<WatchlistType>("stock");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<SearchResult[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState<{ symbol: string; type: WatchlistType } | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Autocomplete search, filtered to the selected type. Also re-runs when
  // `type` changes (not just `symbol`) so flipping stock/crypto/forex while
  // text is already typed refreshes the dropdown immediately rather than
  // waiting for the next keystroke.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!symbol.trim() || symbol.length < 1) {
      setSuggestions([]);
      setShowDropdown(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const results = await api.searchTicker(symbol.trim(), type);
        setSuggestions(results);
        setShowDropdown(results.length > 0);
      } catch {
        setSuggestions([]);
      } finally {
        setSearching(false);
      }
    }, 350);
  }, [symbol, type]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current && !inputRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function selectSuggestion(s: SearchResult) {
    setSymbol(s.symbol);
    setType(s.type);
    setSuggestions([]);
    setShowDropdown(false);
    inputRef.current?.focus();
  }

  async function handleAdd() {
    if (!symbol.trim()) return;
    setLoading(true);
    try {
      await api.addToWatchlist(symbol.trim().toUpperCase(), type);
      setSymbol("");
      setSuggestions([]);
      setShowDropdown(false);
      onUpdate();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleRemove(sym: string, e: React.MouseEvent) {
    e.stopPropagation();
    onRemoveStart(sym);
    try {
      await api.removeFromWatchlist(sym);
      onUpdate();
    } catch (e) {
      console.error(e);
      onRemoveFailed(sym);
    }
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-2 px-3">
        <div className="w-1.5 h-1.5 rounded-full bg-positive shrink-0" />
        <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-text-tertiary">
          Watchlist
        </span>
      </div>

      {items.map((item) => (
        <div
          key={item.id}
          onClick={() => setSelected({ symbol: item.symbol, type: item.type })}
          className="flex items-center justify-between py-1.5 px-3 group hover:bg-overlay-hover cursor-pointer transition-colors"
        >
          <div className="min-w-0">
            <span className="text-[11px] font-medium text-text-secondary group-hover:text-text-primary transition-colors">
              {item.symbol}
            </span>
            {/* Age is always stated. A price with no timestamp is a lie. */}
            <span className="block text-[9px] text-text-muted">{ageLabel(item.as_of)}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {item.price === null ? (
              <span className="text-[10px] text-text-muted">—</span>
            ) : (
              <div className="text-right">
                <div className="text-[11px] font-semibold text-text-primary tabular-nums leading-none">
                  {item.price.toLocaleString("en-US", { maximumFractionDigits: 2 })}
                </div>
                {item.change_pct !== null && (
                  <div
                    className={`text-[9px] tabular-nums mt-0.5 ${
                      item.change_pct >= 0 ? "text-positive" : "text-negative"
                    }`}
                  >
                    {item.change_pct >= 0 ? "▲" : "▼"} {Math.abs(item.change_pct).toFixed(2)}%
                  </div>
                )}
              </div>
            )}
            <button
              onClick={(e) => handleRemove(item.symbol, e)}
              className="text-text-muted hover:text-negative opacity-0 group-hover:opacity-100 transition-all text-[10px]"
            >
              ✕
            </button>
          </div>
        </div>
      ))}

      <div className="mt-3 px-3 space-y-2">
        {/* Input + dropdown */}
        <div className="relative">
          <Input
            ref={inputRef}
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !showDropdown) handleAdd();
              if (e.key === "Escape") setShowDropdown(false);
            }}
            onFocus={() => { if (suggestions.length > 0) setShowDropdown(true); }}
            placeholder="Add ticker (e.g. RELIANCE)"
            className="h-7 text-[11px] bg-surface border-border-strong text-text-secondary placeholder:text-text-muted rounded-lg pr-6"
          />
          {searching && (
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-text-muted">
              ···
            </span>
          )}

          {showDropdown && suggestions.length > 0 && (
            <div
              ref={dropdownRef}
              className="absolute left-0 right-0 top-full mt-1 bg-surface border border-border-default rounded-xl overflow-hidden z-40 shadow-xl"
            >
              {suggestions.map((s) => (
                <button
                  key={s.symbol}
                  onClick={() => selectSuggestion(s)}
                  className="w-full flex items-center justify-between px-3 py-2 hover:bg-overlay-hover transition-colors text-left"
                >
                  <div className="min-w-0">
                    <span className="text-[12px] font-semibold text-text-primary">{s.symbol}</span>
                    <span className="text-[10px] text-text-tertiary ml-1.5 truncate">{s.name}</span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0 ml-2">
                    <span className="text-[9px] text-text-muted">{s.exchange}</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${
                      s.type === "stock" ? "bg-accent/10 text-accent" :
                      s.type === "crypto" ? "bg-warning/10 text-warning" :
                      "bg-info/10 text-info"
                    }`}>
                      {s.type}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex gap-1">
          {(["stock", "crypto", "forex"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setType(t)}
              className={`text-[10px] px-2 py-0.5 rounded-full transition-colors ${
                type === t
                  ? "bg-invert-surface text-invert-text font-semibold"
                  : "bg-surface text-text-tertiary hover:text-text-secondary border border-border-strong"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        <Button
          onClick={handleAdd}
          disabled={loading || !symbol.trim()}
          className="w-full h-7 text-[11px] bg-invert-surface text-invert-text hover:opacity-90 rounded-full font-semibold"
        >
          {loading ? "Adding..." : "Add"}
        </Button>
      </div>

      {selected && (
        <TickerModal
          symbol={selected.symbol}
          type={selected.type}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
