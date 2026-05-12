import { NewsItem } from "@/types";

const CATEGORY_CONFIG = {
  trading: {
    label: "Trading",
    badge: "bg-[#ff5530]/10 text-[#ff5530] border border-[#ff5530]/20",
    dot: "bg-[#ff5530]",
  },
  tech: {
    label: "AI & Tech",
    badge: "bg-[#3b82f6]/10 text-[#3b82f6] border border-[#3b82f6]/20",
    dot: "bg-[#3b82f6]",
  },
  energy: {
    label: "Energy",
    badge: "bg-[#f97316]/10 text-[#f97316] border border-[#f97316]/20",
    dot: "bg-[#f97316]",
  },
};

interface Props {
  item: NewsItem;
}

export function NewsCard({ item }: Props) {
  const config = CATEGORY_CONFIG[item.category];
  const timeStr = item.published_at
    ? new Date(item.published_at).toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block bg-[#111111] border border-[#1e1e1e] rounded-2xl p-4 hover:border-[#2e2e2e] hover:bg-[#151515] transition-all duration-150"
    >
      <div className="flex items-center justify-between mb-2.5">
        <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-semibold ${config.badge}`}>
          {config.label}
        </span>
        <span className="text-[11px] text-[#555]">{timeStr}</span>
      </div>

      <h3 className="text-[13px] font-semibold text-[#d5d5d5] leading-[1.45] line-clamp-2 group-hover:text-white transition-colors">
        {item.title}
      </h3>

      {item.summary && item.summary !== item.title && (
        <p className="text-[12px] text-[#7a7a7a] leading-relaxed mt-1.5 line-clamp-3">
          {item.summary}
        </p>
      )}

      <div className="flex items-center gap-1.5 mt-3">
        <div className={`w-1 h-1 rounded-full shrink-0 ${config.dot}`} />
        <span className="text-[11px] text-[#555] truncate">{item.source}</span>
      </div>
    </a>
  );
}
