import { FeedEvent } from "@/types";

const SEVERITY_DOT: Record<number, string> = {
  1: "bg-text-muted",
  2: "bg-warning",
  3: "bg-accent",
};

function num(value: unknown): number {
  return typeof value === "number" ? value : 0;
}

function signed(value: number, digits = 1): string {
  return `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(digits)}%`;
}

// Narration is a deterministic template per kind, filled from the payload the
// detector recorded. No generation at read time — the sentence a user sees
// must be reproducible from the row.
export function narrate(event: FeedEvent): string {
  const p = event.payload;
  switch (event.kind) {
    case "BIG_MOVE":
      return `Moved ${signed(num(p.move_pct))} — ${num(p.multiple).toFixed(1)}× its normal daily range`;
    case "VOLUME_SPIKE":
      return `Traded ${num(p.ratio).toFixed(1)}× its normal volume`;
    case "RANGE_BREAK":
      return p.scope === "52w"
        ? `New 52-week ${p.direction === "high" ? "high" : "low"}`
        : `Broke ${p.direction === "high" ? "above" : "below"} its 20-day range`;
    case "GAP":
      return `Gapped ${signed(num(p.gap_pct))} at the open`;
    default:
      return event.kind;
  }
}

export function chips(event: FeedEvent): string[] {
  const p = event.payload;
  switch (event.kind) {
    case "BIG_MOVE":
      return [signed(num(p.move_pct)), `${num(p.multiple).toFixed(1)}× range`];
    case "VOLUME_SPIKE":
      return [`${num(p.ratio).toFixed(1)}× vol`];
    case "RANGE_BREAK":
      return [`${p.scope} ${p.direction}`];
    case "GAP":
      return [`gap ${signed(num(p.gap_pct))}`];
    default:
      return [];
  }
}

export function EventRow({ event, unseen }: { event: FeedEvent; unseen: boolean }) {
  const time = new Date(event.occurred_at).toLocaleDateString("en-IN", {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <article
      className={`flex gap-3 px-4 py-3.5 border-b border-border-subtle transition-colors ${
        unseen ? "bg-surface-hover" : ""
      }`}
    >
      <div className={`w-1.5 h-1.5 rounded-full shrink-0 mt-2 ${SEVERITY_DOT[event.severity]}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <span
            className={`text-[12px] font-semibold tracking-tight ${
              unseen ? "text-text-primary" : "text-text-secondary"
            }`}
          >
            {event.symbol}
          </span>
          <time className="text-[10px] text-text-muted shrink-0">{time}</time>
        </div>
        <p className={`text-[12px] mt-0.5 ${unseen ? "text-text-secondary" : "text-text-tertiary"}`}>
          {narrate(event)}
        </p>
        <div className="flex flex-wrap gap-1.5 mt-2">
          {chips(event).map((chip) => (
            <span
              key={chip}
              className="text-[10px] text-text-tertiary bg-surface border border-border-default rounded-full px-2 py-0.5 tabular-nums"
            >
              {chip}
            </span>
          ))}
        </div>
      </div>
    </article>
  );
}
