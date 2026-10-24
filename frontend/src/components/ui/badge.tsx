import type { ReactNode } from "react";

import { cn } from "../../utils/cn";

type BadgeVariant = "ok" | "warn" | "danger" | "info" | "neutral" | "outline";

const variantClasses: Record<BadgeVariant, string> = {
  ok: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  warn: "bg-amber-50 text-amber-700 ring-amber-600/20",
  danger: "bg-red-50 text-red-700 ring-red-600/20",
  info: "bg-brand-50 text-brand-700 ring-brand-600/20",
  neutral: "bg-slate-100 text-slate-600 ring-slate-500/20",
  outline: "bg-white text-slate-600 ring-slate-300",
};

export function Badge({
  children,
  variant = "neutral",
  className,
}: {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        variantClasses[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
