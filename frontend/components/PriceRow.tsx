// frontend/components/PriceRow.tsx
import { MarketPrice } from "@/types";

interface Props {
  item: MarketPrice;
}

export function PriceRow({ item }: Props) {
  const isUp = item.change_pct >= 0;
  const changeColor = isUp ? "text-emerald-400" : "text-red-400";
  const arrow = isUp ? "▲" : "▼";

  return (
    <div className="flex items-center justify-between py-1 px-2 rounded hover:bg-white/5 transition-colors">
      <span className="text-slate-300 text-sm font-mono font-medium">{item.symbol}</span>
      <div className="text-right">
        <div className="text-white text-sm font-mono">
          {item.price.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
        </div>
        <div className={`text-xs font-mono ${changeColor}`}>
          {arrow} {Math.abs(item.change_pct).toFixed(2)}%
        </div>
      </div>
    </div>
  );
}
