import { Inbox } from "lucide-react";

import { cn } from "../../utils/cn";

export function EmptyState({
  title,
  description,
  className,
}: {
  title: string;
  description?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 py-10 text-center", className)}>
      <Inbox aria-hidden className="h-8 w-8 text-slate-300" />
      <p className="text-sm font-medium text-slate-600">{title}</p>
      {description && <p className="max-w-md text-xs text-slate-500">{description}</p>}
    </div>
  );
}
