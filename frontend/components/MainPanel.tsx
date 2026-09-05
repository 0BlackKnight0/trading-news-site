"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useInterval } from "@/hooks/useInterval";
import { Feed } from "./Feed";
import { NewsPanel } from "./NewsPanel";

type Tab = "news" | "changes";

export function MainPanel({ onToggleSidebar }: { onToggleSidebar: () => void }) {
  const [tab, setTab] = useState<Tab>("news");
  const [changesUnread, setChangesUnread] = useState(0);

  // The Changes badge has to stay live while the user is on News, otherwise a
  // firing detector is invisible until they happen to switch tabs.
  useEffect(() => {
    api.getFeed().then((d) => setChangesUnread(d.unread_count)).catch(() => {});
  }, [tab]);
  useInterval(() => {
    api.getFeed().then((d) => setChangesUnread(d.unread_count)).catch(() => {});
  }, 120_000);

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
        <nav className="flex gap-1" role="tablist">
          {(["news", "changes"] as const).map((key) => (
            <button
              key={key}
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
              className={`text-[12px] px-3 py-1 rounded-full transition-colors capitalize ${
                tab === key
                  ? "bg-white/10 text-white font-semibold"
                  : "text-[#666] hover:text-[#aaa]"
              }`}
            >
              {key}
              {key === "changes" && changesUnread > 0 && (
                <span className="ml-1.5 text-[10px] text-[#ff5530]">{changesUnread}</span>
              )}
            </button>
          ))}
        </nav>
      </header>

      <div className="flex-1 overflow-y-auto">
        {tab === "news" ? <NewsPanel /> : <Feed embedded />}
      </div>
    </main>
  );
}
