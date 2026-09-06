"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { HistoryBar } from "@/types";
import { api } from "@/lib/api";

const PLAY_STEP_MS = 400;
const CHART_HEIGHT = 64;

interface Props {
  symbol: string;
}

export function RewindScrubber({ symbol }: Props) {
  const [bars, setBars] = useState<HistoryBar[]>([]);
  const [lastSeenAt, setLastSeenAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const playRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    api.getHistory(symbol)
      .then((data) => {
        if (cancelled) return;
        setBars(data.bars);
        setLastSeenAt(data.last_seen_at);
        setIndex(data.bars.length > 0 ? data.bars.length - 1 : 0);
      })
      .catch(() => { if (!cancelled) { setBars([]); setFailed(true); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [symbol]);

  // Play steps the handle forward one day at a time until it reaches the
  // end, so the line "grows" and reads as a replay rather than a jump-cut.
  useEffect(() => {
    if (!playing) return;
    playRef.current = setInterval(() => {
      setIndex((i) => {
        if (i >= bars.length - 1) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, PLAY_STEP_MS);
    return () => { if (playRef.current) clearInterval(playRef.current); };
  }, [playing, bars.length]);

  const visible = bars.slice(0, index + 1);

  const points = useMemo(() => {
    if (visible.length < 2) return "";
    const closes = visible.map((b) => b.close);
    const min = Math.min(...closes);
    const max = Math.max(...closes);
    const span = max - min || 1;
    const width = 100;
    return visible
      .map((b, i) => {
        const x = (i / (visible.length - 1)) * width;
        const y = CHART_HEIGHT - ((b.close - min) / span) * CHART_HEIGHT;
        return `${x},${y.toFixed(2)}`;
      })
      .join(" ");
  }, [visible]);

  if (loading) {
    return <div className="h-24 bg-[#161616] border border-[#1e1e1e] rounded-xl animate-pulse" />;
  }

  if (failed) {
    return (
      <div className="bg-[#161616] border border-[#1e1e1e] rounded-xl p-3">
        <p className="text-[11px] text-[#f59e0b]">Couldn&apos;t load history for {symbol}.</p>
      </div>
    );
  }

  if (bars.length < 2) {
    return (
      <div className="bg-[#161616] border border-[#1e1e1e] rounded-xl p-3">
        <p className="text-[11px] text-[#444]">Not enough history yet to rewind {symbol}.</p>
      </div>
    );
  }

  const current = bars[index];

  return (
    <div className="bg-[#161616] border border-[#1e1e1e] rounded-xl p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] text-[#555] uppercase tracking-wider">Rewind</span>
        <span className="text-[11px] text-[#888] tabular-nums">
          {new Date(current.ts).toLocaleDateString("en-IN", { month: "short", day: "numeric" })}
          {" · "}
          {current.close.toLocaleString("en-US", { maximumFractionDigits: 2 })}
        </span>
      </div>

      <svg viewBox={`0 0 100 ${CHART_HEIGHT}`} preserveAspectRatio="none" className="w-full h-16">
        {/* The last-visit marker: bars[0] IS last_seen_at, since the range
            always starts there — so it always sits at the chart's left edge. */}
        <line x1={0.5} y1={0} x2={0.5} y2={CHART_HEIGHT} stroke="#3a3a3a" strokeDasharray="2,2" strokeWidth={1} vectorEffect="non-scaling-stroke" />
        {points && (
          <polyline points={points} fill="none" stroke="#22c55e" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
        )}
      </svg>

      <div className="flex items-center gap-2 mt-2">
        <button
          onClick={() => {
            if (!playing && index >= bars.length - 1) setIndex(0);
            setPlaying((p) => !p);
          }}
          className="text-[11px] text-[#888] hover:text-white transition-colors w-5 text-center shrink-0"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? "⏸" : "▶"}
        </button>
        <input
          type="range"
          min={0}
          max={bars.length - 1}
          value={index}
          onChange={(e) => { setPlaying(false); setIndex(Number(e.target.value)); }}
          className="flex-1 accent-[#22c55e]"
        />
      </div>
      {lastSeenAt && (
        <p className="text-[9px] text-[#3a3a3a] mt-1">
          Since your last visit — {new Date(lastSeenAt).toLocaleDateString("en-IN", { month: "short", day: "numeric" })}
        </p>
      )}
    </div>
  );
}
