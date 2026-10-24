import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "../../utils/cn";

export function Pagination({
  offset,
  limit,
  count,
  total,
  nextOffset,
  onPage,
  disabled,
}: {
  offset: number;
  limit: number;
  count: number;
  total: number | null;
  nextOffset: number | null;
  onPage: (offset: number) => void;
  disabled?: boolean;
}) {
  const hasPrev = offset > 0;
  const hasNext = nextOffset != null && nextOffset < (total ?? Infinity);
  const start = total != null && total > 0 ? offset + 1 : 0;
  const end = offset + count;
  return (
    <div className="flex items-center justify-between gap-3 border-t border-surface-border px-4 py-2 text-xs text-slate-500">
      <span>
        {total != null ? `第 ${start}-${end} 条，共 ${total} 条` : `本页 ${count} 条`}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={disabled || !hasPrev}
          onClick={() => onPage(Math.max(0, offset - limit))}
          className={cn(
            "inline-flex items-center gap-1 rounded-md border border-surface-border px-2 py-1 hover:bg-surface-muted",
            (disabled || !hasPrev) && "cursor-not-allowed opacity-40",
          )}
        >
          <ChevronLeft className="h-3.5 w-3.5" /> 上一页
        </button>
        <button
          type="button"
          disabled={disabled || !hasNext}
          onClick={() => onPage(nextOffset ?? offset + limit)}
          className={cn(
            "inline-flex items-center gap-1 rounded-md border border-surface-border px-2 py-1 hover:bg-surface-muted",
            (disabled || !hasNext) && "cursor-not-allowed opacity-40",
          )}
        >
          下一页 <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
