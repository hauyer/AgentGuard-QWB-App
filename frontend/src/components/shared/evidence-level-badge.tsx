import { cn } from "../../utils/cn";

export type EvidenceLevel = "synthetic" | "observational" | "interventional" | "causal_validated" | "unknown";

const LEVEL_META: Record<
  EvidenceLevel,
  { label: string; className: string; description: string }
> = {
  synthetic: {
    label: "SYNTHETIC",
    className: "bg-slate-100 text-slate-600 ring-slate-500/20",
    description: "明确生成的教学或演示数据",
  },
  observational: {
    label: "OBSERVATIONAL",
    className: "bg-blue-50 text-blue-700 ring-blue-600/20",
    description: "观测性结果，未经过因果干预验证",
  },
  interventional: {
    label: "INTERVENTIONAL",
    className: "bg-amber-50 text-amber-700 ring-amber-600/20",
    description: "包含干预动作的结果，仍非因果已验证",
  },
  causal_validated: {
    label: "CAUSAL_VALIDATED",
    className: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    description: "经过因果验证（必须附带验证依据）",
  },
  unknown: {
    label: "UNKNOWN",
    className: "bg-slate-100 text-slate-600 ring-slate-500/20",
    description: "上游未提供可识别的证据等级",
  },
};

export function EvidenceLevelBadge({ level }: { level: string }) {
  const meta = LEVEL_META[level as EvidenceLevel] ?? {
    label: level.toUpperCase(),
    className: "bg-slate-100 text-slate-600 ring-slate-500/20",
    description: undefined as string | undefined,
  };
  return (
    <span
      title={meta.description}
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset",
        meta.className,
      )}
    >
      {meta.label}
    </span>
  );
}
