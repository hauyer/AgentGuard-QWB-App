import { cn } from "../../utils/cn";

export type VerificationStatus = "verified" | "unverified" | "blocked" | "failed" | "unsupported";

const STATUS_META: Record<VerificationStatus, { label: string; className: string }> = {
  verified: { label: "已验证", className: "bg-emerald-50 text-emerald-700 ring-emerald-600/20" },
  unverified: { label: "未验证", className: "bg-slate-100 text-slate-600 ring-slate-500/20" },
  blocked: { label: "验证阻塞", className: "bg-amber-50 text-amber-700 ring-amber-600/20" },
  failed: { label: "验证失败", className: "bg-red-50 text-red-700 ring-red-600/20" },
  unsupported: { label: "不支持", className: "bg-slate-100 text-slate-500 ring-slate-500/20" },
};

export function VerificationBadge({ status }: { status: string }) {
  const meta = STATUS_META[status as VerificationStatus] ?? {
    label: status,
    className: "bg-slate-100 text-slate-600 ring-slate-500/20",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset",
        meta.className,
      )}
    >
      {meta.label}
    </span>
  );
}
