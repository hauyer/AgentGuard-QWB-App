import { useMemo, useState } from "react";

import { cn } from "../../utils/cn";

/** Collapsible JSON contract viewer used for evidence payloads and raw API bodies. */
export function JsonViewer({
  value,
  label,
  defaultExpanded = false,
  maxHeight = "max-h-80",
}: {
  value: unknown;
  label?: string;
  defaultExpanded?: boolean;
  maxHeight?: string;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const text = useMemo(() => JSON.stringify(value, null, 2), [value]);
  return (
    <div className="overflow-hidden rounded-md border border-surface-border bg-slate-950">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between px-3 py-2 text-left font-mono text-xs text-slate-300 hover:bg-slate-900"
      >
        <span className="truncate">{label ?? "JSON 合同"}</span>
        <span className="ml-2 shrink-0 text-slate-500">{expanded ? "收起" : "展开"}</span>
      </button>
      {expanded && (
        <pre className={cn("overflow-auto px-3 pb-3 text-[11px] leading-relaxed text-slate-300", maxHeight)}>
          {text}
        </pre>
      )}
    </div>
  );
}
