"use client";
import { useEffect, useState } from "react";
import { TickerDetail, WatchlistType } from "@/types";
import { api } from "@/lib/api";
import { RewindScrubber } from "./RewindScrubber";

interface Props {
  symbol: string;
  type: WatchlistType;
  onClose: () => void;
}

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", { maximumFractionDigits: decimals });
}

function fmtLarge(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return `$${n.toLocaleString()}`;
}

function fmtVol(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toString();
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface border border-border-default rounded-xl p-3">
      <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">{label}</p>
      <p className="text-[13px] font-semibold text-text-primary">{value}</p>
    </div>
  );
}

export function TickerModal({ symbol, type, onClose }: Props) {
  const [data, setData] = useState<TickerDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setData(null);
    api.getTickerDetail(symbol, type)
      .then(setData)
      .catch(() => setData({ symbol, name: symbol, price: 0, change_pct: 0, change_abs: 0, currency: "USD", market_cap: null, volume: null, pe_ratio: null, week_52_high: null, week_52_low: null, open: null, prev_close: null, news: [], error: "Failed to load" }))
      .finally(() => setLoading(false));
  }, [symbol, type]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const isUp = (data?.change_pct ?? 0) >= 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.75)", backdropFilter: "blur(4px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-2xl bg-surface border border-border-default rounded-2xl md:rounded-3xl overflow-hidden max-h-[92vh] md:max-h-[88vh] flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between px-4 md:px-6 pt-4 md:pt-6 pb-4 border-b border-border-default shrink-0">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] font-semibold bg-text-primary/10 text-text-primary px-2.5 py-0.5 rounded-full">
                {symbol}
              </span>
              <span className="text-[11px] text-text-muted capitalize">{type}</span>
            </div>
            <h2 className="text-[16px] font-semibold text-text-primary leading-tight">
              {loading ? "Loading..." : (data?.name || symbol)}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-secondary transition-colors text-lg leading-none mt-0.5"
          >
            ✕
          </button>
        </div>

        <div className="overflow-y-auto flex-1">
          {loading ? (
            <div className="px-4 md:px-6 py-8 space-y-3 animate-pulse">
              <div className="h-10 w-40 bg-surface-hover rounded-xl" />
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="h-16 bg-surface-hover rounded-xl" />
                ))}
              </div>
            </div>
          ) : data?.error && !data.price ? (
            <div className="px-4 md:px-6 py-8 text-text-tertiary text-sm">{data.error}</div>
          ) : data ? (
            <div className="px-4 md:px-6 py-4 md:py-5 space-y-4 md:space-y-5">
              {/* Price block */}
              <div className="flex flex-wrap items-end gap-3">
                <span className="text-[30px] md:text-[36px] font-bold text-text-primary leading-none tabular-nums">
                  {data.currency !== "USD" ? "" : "$"}{fmt(data.price, data.price > 100 ? 2 : 4)}
                  {data.currency !== "USD" && (
                    <span className="text-[18px] text-text-tertiary ml-1">{data.currency}</span>
                  )}
                </span>
                <div className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-[12px] font-semibold mb-1 ${
                  isUp ? "bg-positive/10 text-positive" : "bg-negative/10 text-negative"
                }`}>
                  {isUp ? "▲" : "▼"} {Math.abs(data.change_pct).toFixed(2)}%
                  <span className="opacity-70 ml-0.5">
                    ({isUp ? "+" : ""}{fmt(data.change_abs, 2)})
                  </span>
                </div>
              </div>

              <RewindScrubber symbol={symbol} />

              {/* Stats grid */}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                <StatCell label="Market Cap" value={fmtLarge(data.market_cap)} />
                <StatCell label="Volume" value={fmtVol(data.volume)} />
                <StatCell label="P/E Ratio" value={data.pe_ratio ? fmt(data.pe_ratio) : "—"} />
                <StatCell label="52W High" value={data.week_52_high ? `$${fmt(data.week_52_high)}` : "—"} />
                <StatCell label="52W Low" value={data.week_52_low ? `$${fmt(data.week_52_low)}` : "—"} />
                <StatCell label="Prev Close" value={data.prev_close ? `$${fmt(data.prev_close)}` : "—"} />
              </div>

              {/* News */}
              {data.news.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-info" />
                    <h3 className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary">
                      Recent News
                    </h3>
                  </div>
                  <div className="space-y-2">
                    {data.news.map((item, i) => (
                      <a
                        key={i}
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block bg-surface border border-border-default rounded-xl p-3.5 hover:border-border-strong hover:bg-surface-hover transition-all group"
                      >
                        <p className="text-[12px] font-semibold text-text-secondary group-hover:text-text-primary leading-snug line-clamp-2 transition-colors">
                          {item.title}
                        </p>
                        {item.summary && item.summary !== item.title && (
                          <p className="text-[11px] text-text-tertiary mt-1 line-clamp-2 leading-relaxed">
                            {item.summary}
                          </p>
                        )}
                        <div className="flex items-center gap-1.5 mt-2">
                          <div className="w-1 h-1 rounded-full bg-info" />
                          <span className="text-[10px] text-text-muted">{item.source}</span>
                          {item.published_at && (
                            <span className="text-[10px] text-text-muted ml-auto">
                              {new Date(item.published_at).toLocaleDateString("en-IN", {
                                month: "short", day: "numeric",
                              })}
                            </span>
                          )}
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {data.news.length === 0 && (
                <p className="text-[12px] text-text-muted py-2">No recent news found for {symbol}.</p>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
