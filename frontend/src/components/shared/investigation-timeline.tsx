import { CheckCircle2, Circle, CircleDashed, XCircle } from "lucide-react";

import { cn } from "../../utils/cn";

export interface TimelineEvent {
  step: string;
  label: string;
  status: "completed" | "running" | "pending" | "blocked" | "failed";
  at?: string | null;
  detail?: string;
}

const STATUS_ICON = {
  completed: CheckCircle2,
  running: CircleDashed,
  pending: Circle,
  blocked: XCircle,
  failed: XCircle,
} as const;

const STATUS_TONE = {
  completed: "text-emerald-600",
  running: "text-brand-600",
  pending: "text-slate-300",
  blocked: "text-amber-600",
  failed: "text-red-600",
} as const;

/**
 * Investigation workflow timeline. Only steps confirmed by real fields or
 * recorded events are marked completed/running; everything else stays pending
 * with an explicit "未确认" hint. Never guesses that a step has finished.
 */
export function InvestigationTimeline({ events }: { events: TimelineEvent[] }) {
  return (
    <ol className="space-y-0">
      {events.map((event, index) => {
        const Icon = STATUS_ICON[event.status];
        return (
          <li key={event.step} className="relative flex gap-3 pb-4 last:pb-0">
            {index < events.length - 1 && (
              <span aria-hidden className="absolute left-[7px] top-4 h-full w-px bg-surface-border" />
            )}
            <Icon aria-hidden className={cn("relative z-10 mt-0.5 h-3.5 w-3.5 shrink-0 bg-surface", STATUS_TONE[event.status])} />
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-medium text-slate-700">{event.label}</span>
                {event.at && <span className="font-mono text-[11px] text-slate-400">{event.at}</span>}
              </div>
              {event.status === "pending" && (
                <p className="text-[11px] text-slate-400">未确认（当前数据不包含该步骤完成证据）</p>
              )}
              {event.detail && <p className="mt-0.5 text-xs text-slate-500">{event.detail}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
