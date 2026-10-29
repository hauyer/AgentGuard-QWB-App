import type { ReactNode } from "react";

import { cn } from "../../utils/cn";

export function Card({
  children,
  className,
  title,
  description,
  action,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <section
      className={cn(
        "min-w-0 max-w-full rounded-lg border border-surface-border bg-surface",
        className,
      )}
    >
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 border-b border-surface-border px-4 py-3">
          <div className="min-w-0 break-words">
            {title && <h2 className="text-[13px] font-semibold text-slate-800">{title}</h2>}
            {description && <p className="mt-0.5 max-w-3xl text-xs leading-5 text-slate-500">{description}</p>}
          </div>
          {action}
        </header>
      )}
      <div className="min-w-0 p-3 sm:p-4">{children}</div>
    </section>
  );
}
