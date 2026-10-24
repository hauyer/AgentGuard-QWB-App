import type { ReactNode } from "react";

import { Card } from "../ui/card";
import { Skeleton } from "./skeleton";

export function MetricCard({
  title,
  value,
  hint,
  unavailable,
  tone = "default",
}: {
  title: string;
  value?: ReactNode;
  hint?: string;
  unavailable?: boolean;
  tone?: "default" | "danger" | "warn" | "ok";
}) {
  const toneClass =
    tone === "danger" ? "text-red-700" : tone === "warn" ? "text-amber-700" : tone === "ok" ? "text-emerald-700" : "text-slate-800";
  return (
    <Card title={title}>
      <div className="flex flex-col gap-1">
        {unavailable ? (
          <span className="text-sm font-medium text-slate-400">不可用</span>
        ) : (
          <span className={toneClass}>{value}</span>
        )}
        {hint && <span className="text-[11px] text-slate-500">{hint}</span>}
      </div>
    </Card>
  );
}

export function MetricCardSkeleton({ title }: { title: string }) {
  return (
    <Card title={title}>
      <Skeleton className="h-5 w-16" />
    </Card>
  );
}
