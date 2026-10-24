import { cn } from "../../utils/cn";
import { Spinner } from "./spinner";

export function LoadingState({ label, className }: { label?: string; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2 py-6 text-sm text-slate-500", className)} role="status">
      <Spinner />
      <span>{label ?? "加载中…"}</span>
    </div>
  );
}
