// The whole product in one component: a line marking where the user stopped
// reading. Everything above it is new since their last visit.
export function Divider({ lastSeenAt }: { lastSeenAt: string }) {
  const label = new Date(lastSeenAt).toLocaleString("en-IN", {
    weekday: "long",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="flex items-center gap-3 px-4 py-3" role="separator">
      <div className="h-px flex-1 bg-[#ff5530]/25" />
      <span className="text-[10px] uppercase tracking-[0.12em] text-[#ff5530]/70 shrink-0">
        {label} — your last visit
      </span>
      <div className="h-px flex-1 bg-[#ff5530]/25" />
    </div>
  );
}
