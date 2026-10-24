import type { ReactNode } from "react";

import { cn } from "../../utils/cn";
import { EmptyState } from "../ui/empty-state";
import { LoadingState } from "../ui/loading-state";
import { Pagination } from "../ui/pagination";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  className?: string;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  emptyTitle,
  emptyDescription,
  error,
  offset,
  limit,
  count,
  total,
  nextOffset,
  onPage,
  pageDisabled,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  emptyTitle: string;
  emptyDescription?: string;
  error?: ReactNode;
  offset: number;
  limit: number;
  count: number;
  total: number | null;
  nextOffset: number | null;
  onPage: (offset: number) => void;
  pageDisabled?: boolean;
}) {
  if (loading) return <LoadingState label="加载数据…" />;
  if (error) return <div className="p-2">{error}</div>;
  if (rows.length === 0) return <EmptyState title={emptyTitle} description={emptyDescription} />;
  return (
    <div className="overflow-hidden rounded-lg border border-surface-border bg-surface shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-surface-border bg-surface-muted/60 text-xs text-slate-500">
            <tr>
              {columns.map((column) => (
                <th key={column.key} className={cn("px-3 py-2 font-medium", column.className)}>
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border">
            {rows.map((row) => (
              <tr key={rowKey(row)} className="hover:bg-surface-muted/40">
                {columns.map((column) => (
                  <td key={column.key} className={cn("px-3 py-2 align-top", column.className)}>
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination
        offset={offset}
        limit={limit}
        count={count}
        total={total}
        nextOffset={nextOffset}
        onPage={onPage}
        disabled={pageDisabled}
      />
    </div>
  );
}
