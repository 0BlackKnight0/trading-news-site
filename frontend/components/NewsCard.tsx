import { NewsItem } from "@/types";

const CATEGORY_CONFIG = {
  trading: { label: "Trading", color: "bg-indigo-600 text-white" },
  tech: { label: "AI & Tech", color: "bg-emerald-600 text-white" },
  energy: { label: "Energy", color: "bg-orange-500 text-white" },
};

interface Props {
  item: NewsItem;
}

export function NewsCard({ item }: Props) {
  const config = CATEGORY_CONFIG[item.category];
  const timeAgo = item.published_at
    ? new Date(item.published_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
    : "";

  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-[#13151f] border border-slate-800 rounded-lg p-3 hover:border-slate-600 hover:bg-[#1a1d2e] transition-all"
    >
      <div className="flex items-start gap-2 mb-2">
        <span className={`text-xs px-2 py-0.5 rounded font-medium shrink-0 ${config.color}`}>
          {config.label}
        </span>
        <span className="text-xs text-slate-500 ml-auto shrink-0">{timeAgo}</span>
      </div>
      <p className="text-sm text-slate-200 leading-snug line-clamp-2">{item.title}</p>
      <p className="text-xs text-slate-500 mt-1">{item.source}</p>
    </a>
  );
}
