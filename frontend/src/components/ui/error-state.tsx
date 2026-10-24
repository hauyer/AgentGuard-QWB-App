import { AlertTriangle, RefreshCw, ServerCrash } from "lucide-react";

import { cn } from "../../utils/cn";
import { Button } from "./button";

export type ErrorStateKind = "backend" | "permission" | "generic";

const KIND_META: Record<
  ErrorStateKind,
  { icon: typeof AlertTriangle; title: string; tone: "red" | "amber" }
> = {
  backend: { icon: ServerCrash, title: "后端不可用", tone: "red" },
  permission: { icon: AlertTriangle, title: "权限不足", tone: "amber" },
  generic: { icon: AlertTriangle, title: "请求失败", tone: "amber" },
};

export function ErrorState({
  kind = "generic",
  message,
  code,
  requestId,
  onRetry,
  retrying,
  children,
}: {
  kind?: ErrorStateKind;
  message?: string;
  code?: string;
  requestId?: string | null;
  onRetry?: () => void;
  retrying?: boolean;
  children?: React.ReactNode;
}) {
  const meta = KIND_META[kind];
  const Icon = meta.icon;
  const toneText = meta.tone === "red" ? "text-red-700" : "text-amber-700";
  return (
    <div className="flex flex-col items-start gap-3 rounded-lg border border-surface-border bg-surface p-4">
      <div className={cn("flex items-center gap-2 text-sm font-medium", toneText)}>
        <Icon aria-hidden className="h-5 w-5" />
        <span>{message ?? meta.title}</span>
      </div>
      {(code || requestId) && (
        <p className="font-mono text-xs text-slate-500">
          {code && <span>错误码：{code}</span>}
          {requestId && <span className="ml-2">Request ID：{requestId}</span>}
        </p>
      )}
      {children}
      {onRetry && (
        <Button variant="secondary" onClick={onRetry} disabled={retrying}>
          <RefreshCw aria-hidden className={cn("mr-1 h-3.5 w-3.5", retrying && "animate-spin")} />
          {retrying ? "重试中…" : "重试"}
        </Button>
      )}
    </div>
  );
}
