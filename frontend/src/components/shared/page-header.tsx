import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  actions,
  level = 1,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  level?: 1 | 2;
}) {
  const Heading = level === 1 ? "h1" : "h2";
  return (
    <div className="flex flex-col gap-3 border-b border-surface-border/70 pb-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <Heading className="text-xl font-semibold tracking-tight text-slate-900">{title}</Heading>
        {description && <p className="mt-1 max-w-3xl text-[13px] leading-5 text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
