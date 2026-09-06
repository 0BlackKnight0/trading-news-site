import { useEffect, useState } from "react";
import { MarketPrice, WatchlistType } from "@/types";

interface Props {
  item: MarketPrice;
  alreadyWatched: boolean;
  onAdd?: (symbol: string, type: WatchlistType) => Promise<void>;
}

function formatPrice(price: number, symbol: string): string {
  if (symbol.includes("/")) return price.toLocaleString("en-US", { maximumFractionDigits: 4 });
  if (price > 10000) return price.toLocaleString("en-IN", { maximumFractionDigits: 0 });
  if (price > 100) return price.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return price.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

export function PriceRow({ item, alreadyWatched, onAdd }: Props) {
  const isUp = item.change_pct >= 0;
  const [adding, setAdding] = useState(false);

  // Once the parent's watchlist re-fetch confirms this symbol is tracked,
  // drop the transient "adding" spinner in favour of the persistent
  // already-watched checkmark.
  useEffect(() => {
    if (alreadyWatched) setAdding(false);
  }, [alreadyWatched]);

  async function handleAdd(e: React.MouseEvent) {
    e.stopPropagation();
    if (!onAdd || !item.watchlist_symbol || !item.watchlist_type) return;
    setAdding(true);
    try {
      await onAdd(item.watchlist_symbol, item.watchlist_type);
    } catch (err) {
      console.error(err);
      setAdding(false);
    }
  }

  const canAdd = !!(onAdd && item.watchlist_symbol && item.watchlist_type);

  return (
    <div className="flex items-center justify-between py-1.5 px-3 hover:bg-overlay-hover transition-colors cursor-default group">
      <span className="text-[11px] font-medium text-text-secondary group-hover:text-text-primary transition-colors truncate max-w-[95px]">
        {item.symbol}
      </span>
      <div className="flex items-center gap-1.5 shrink-0">
        <div className="text-right">
          <div className="text-[12px] font-semibold text-text-primary tabular-nums leading-none">
            {formatPrice(item.price, item.symbol)}
          </div>
          <div className={`text-[10px] tabular-nums font-medium mt-0.5 ${isUp ? "text-positive" : "text-negative"}`}>
            {isUp ? "▲" : "▼"} {Math.abs(item.change_pct).toFixed(2)}%
          </div>
        </div>
        {alreadyWatched ? (
          <span
            className="text-[11px] text-positive w-4 text-center shrink-0"
            title="On your watchlist"
          >
            ✓
          </span>
        ) : canAdd ? (
          <button
            onClick={handleAdd}
            disabled={adding}
            title={`Add ${item.symbol} to your watchlist`}
            className="text-[13px] leading-none text-text-muted hover:text-positive opacity-0 group-hover:opacity-100 transition-all w-4 text-center shrink-0 disabled:opacity-100 disabled:text-text-muted"
          >
            {adding ? "···" : "+"}
          </button>
        ) : (
          <span className="w-4 shrink-0" />
        )}
      </div>
    </div>
  );
}
