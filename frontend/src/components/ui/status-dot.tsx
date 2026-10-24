import { cn } from "../../utils/cn";

type StatusTone = "ok" | "warn" | "danger" | "neutral" | "info";

const toneClasses: Record<StatusTone, string> = {
  ok: "bg-emerald-500",
  warn: "bg-amber-500",
  danger: "bg-red-500",
  neutral: "bg-slate-400",
  info: "bg-brand-500",
};

export function StatusDot({ tone, className }: { tone: StatusTone; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block h-2 w-2 shrink-0 rounded-full", toneClasses[tone], className)}
    />
  );
}
