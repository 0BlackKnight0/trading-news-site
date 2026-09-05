"use client";
import { useCallback, useEffect, useState } from "react";
import { FeedEvent } from "@/types";
import { api } from "@/lib/api";
import { useInterval } from "@/hooks/useInterval";
import { EventRow } from "./EventRow";
import { Divider } from "./Divider";

export function Feed({ onToggleSidebar }: { onToggleSidebar: () => void }) {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [lastSeenAt, setLastSeenAt] = useState<string | null>(null);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.getFeed();
      setEvents(data.events);
      setLastSeenAt(data.last_seen_at);
      setUnread(data.unread_count);
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);
  useInterval(load, 120_000);

  async function catchUp() {
    try {
      const { last_seen_at } = await api.markSeen();
      setLastSeenAt(last_seen_at);
      setUnread(0);
    } catch {
      setFailed(true);
    }
  }

  // Compared against created_at (when the row was written), not occurred_at
  // (the market session timestamp, constant all day) — an intraday
  // re-detection on today's still-forming bar must still count as unread.
  const isUnseen = (event: FeedEvent) =>
    lastSeenAt !== null && event.created_at > lastSeenAt;
  const dividerIndex = events.findIndex((event) => !isUnseen(event));

  return (
    <main className="flex-1 flex flex-col overflow-hidden bg-[#0a0a0a]">
      <header className="px-4 md:px-6 py-4 border-b border-[#191919] flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="md:hidden flex flex-col gap-[5px] p-1 -ml-1 text-[#555] hover:text-[#888] transition-colors"
          aria-label="Toggle market sidebar"
        >
          <span className="block w-[18px] h-[1.5px] bg-current rounded-full" />
          <span className="block w-[18px] h-[1.5px] bg-current rounded-full" />
          <span className="block w-[18px] h-[1.5px] bg-current rounded-full" />
        </button>
        <h1 className="text-[15px] font-semibold text-white tracking-tight">Since</h1>
        {unread > 0 && (
          <span className="text-[10px] font-semibold text-[#ff5530] bg-[#ff5530]/10 border border-[#ff5530]/20 rounded-full px-2 py-0.5">
            {unread} new
          </span>
        )}
        <div className="flex-1" />
        {unread > 0 && (
          <button
            onClick={catchUp}
            className="text-[11px] text-[#777] hover:text-white border border-[#1e1e1e] hover:border-[#2e2e2e] rounded-full px-3 py-1 transition-all"
          >
            Catch up
          </button>
        )}
      </header>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-14 bg-[#111] rounded-xl animate-pulse" />
            ))}
          </div>
        ) : failed ? (
          <p className="text-center text-[12px] text-[#f59e0b] py-16">
            Could not reach the feed. Showing nothing rather than something stale.
          </p>
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-6">
            <p className="text-[15px] font-semibold text-[#c8c8c8]">All quiet.</p>
            <p className="text-[12px] text-[#4a4a4a] mt-1.5">
              Nothing crossed your thresholds
              {lastSeenAt
                ? ` since ${new Date(lastSeenAt).toLocaleDateString("en-IN", {
                    weekday: "long",
                  })}`
                : ""}
              .
            </p>
          </div>
        ) : (
          events.map((event, i) => (
            <div key={event.id}>
              {i === dividerIndex && lastSeenAt && <Divider lastSeenAt={lastSeenAt} />}
              <EventRow event={event} unseen={isUnseen(event)} />
            </div>
          ))
        )}
      </div>
    </main>
  );
}
