import { MarketPrice } from "@/types";

interface Props {
  item: MarketPrice;
}

function formatPrice(price: number, symbol: string): string {
  if (symbol.includes("/")) return price.toLocaleString("en-US", { maximumFractionDigits: 4 });
  if (price > 10000) return price.toLocaleString("en-IN", { maximumFractionDigits: 0 });
  if (price > 100) return price.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return price.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

export function PriceRow({ item }: Props) {
  const isUp = item.change_pct >= 0;

  return (
    <div className="flex items-center justify-between py-1.5 px-3 hover:bg-white/[0.03] transition-colors cursor-default group">
      <span className="text-[11px] font-medium text-[#888] group-hover:text-[#bbb] transition-colors truncate max-w-[95px]">
        {item.symbol}
      </span>
      <div className="text-right">
        <div className="text-[12px] font-semibold text-[#e0e0e0] tabular-nums leading-none">
          {formatPrice(item.price, item.symbol)}
        </div>
        <div className={`text-[10px] tabular-nums font-medium mt-0.5 ${isUp ? "text-[#22c55e]" : "text-[#ef4444]"}`}>
          {isUp ? "▲" : "▼"} {Math.abs(item.change_pct).toFixed(2)}%
        </div>
      </div>
    </div>
  );
}
