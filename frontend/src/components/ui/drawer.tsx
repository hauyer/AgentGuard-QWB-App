import { X } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "../../utils/cn";

/** Right-side detail drawer (evidence details, node/edge metadata). */
export function Drawer({
  open,
  onClose,
  title,
  children,
  footer,
  width = "w-[480px]",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-slate-900/30" onClick={onClose} aria-hidden />
      <div className={cn("relative flex h-full flex-col border-l border-surface-border bg-white shadow-xl", width)}>
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-surface-border px-4">
          <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="rounded p-1 text-slate-500 hover:bg-surface-muted hover:text-slate-700"
          >
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
        {footer && <footer className="shrink-0 border-t border-surface-border p-3">{footer}</footer>}
      </div>
    </div>
  );
}
