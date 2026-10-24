import { cn } from "../../utils/cn";

/** Identifies where a piece of data comes from (AgentGuard live / demo fixture / WARDEN). */
export function SourceBadge({ source, mode }: { source: string; mode?: string }) {
  const isLive = mode === "live" || source === "agentguard" || source === "live";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-mono text-[10px] font-medium ring-1 ring-inset",
        isLive
          ? "bg-brand-50 text-brand-700 ring-brand-600/20"
          : "bg-violet-50 text-violet-700 ring-violet-600/20",
      )}
      title={`数据来源：${source}`}
    >
      <span aria-hidden className={cn("h-1.5 w-1.5 rounded-full", isLive ? "bg-brand-500" : "bg-violet-500")} />
      {source}
    </span>
  );
}
