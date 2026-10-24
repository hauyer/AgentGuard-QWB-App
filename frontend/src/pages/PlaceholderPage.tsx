import { Construction } from "lucide-react";

export function PlaceholderPage({ title, stage }: { title: string; stage: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-surface-border bg-white p-10 text-center">
      <Construction className="h-8 w-8 text-slate-300" />
      <h1 className="text-lg font-semibold text-slate-700">{title}</h1>
      <p className="max-w-md text-sm text-slate-500">
        该模块将在阶段 {stage} 交付。当前版本仅提供真实系统连接状态与基础导航，不展示未经验证的虚构数据。
      </p>
    </div>
  );
}
