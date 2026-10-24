import { useAuthStore } from "../stores/auth-store";
import { useExperiences } from "../hooks/use-reports";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import { VerificationBadge } from "../components/shared/verification-badge";
import type { Experience } from "../types/reports";
import { cn } from "../utils/cn";

export function ExperiencesPage() {
  const role = useAuthStore((state) => state.role);
  const { data, isLoading, error, refetch, isFetching } = useExperiences();

  const items = data?.items ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-4">
      <PageHeader
        title="经验中心"
        description="已验证经验展示与查询。第一版只做展示和查询，不在应用层开发 Thompson Sampling。"
      />

      {isLoading && <p className="text-sm text-slate-400">正在加载经验…</p>}

      {error && (
        <ErrorState
          title="经验中心不可用"
          message={error instanceof Error ? error.message : "无法获取经验数据"}
          code={(error as { code?: string }).code}
          requestId={(error as { requestId?: string | null }).requestId}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      )}

      {data && meta && <DemoBanner meta={meta} />}

      {data && items.length > 0 && (
        <>
          <div className="space-y-3">
            {items.map((item) => (
              <ExperienceCard key={item.experience_id} item={item} />
            ))}
          </div>
          {data.recommendation_note && (
            <p className="text-xs text-amber-700">⚠ {data.recommendation_note}</p>
          )}
        </>
      )}

      {data && items.length === 0 && !error && (
        <Card title="经验中心">
          <p className="text-sm text-slate-400">暂无已验证经验。</p>
        </Card>
      )}

      <p className="text-[11px] text-slate-400">
        当前角色：<span className="font-mono">{role ?? "未登录"}</span>。演示经验不得用于真实因果实验统计。
      </p>
    </div>
  );
}

function ExperienceCard({ item }: { item: Experience }) {
  const recommended = item.recommendation_allowed;
  return (
    <Card title={item.experience_id}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="neutral">{item.risk_type ?? "—"}</Badge>
        <VerificationBadge status={item.verification_level ?? "unverified"} />
        <span
          className={cn(
            "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset",
            recommended ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20" : "bg-slate-100 text-slate-500 ring-slate-500/20",
          )}
        >
          {recommended ? "允许用于推荐" : "不允许推荐"}
        </span>
        <span className="ml-auto font-mono text-[10px] text-slate-400">策略版本：{item.policy_version ?? "—"}</span>
      </div>

      <h3 className="mt-2 text-sm font-semibold text-slate-800">{item.title ?? "—"}</h3>
      <p className="mt-1 text-xs text-slate-600">{item.action ?? "—"}</p>

      <dl className="mt-3 grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-slate-400">适用场景</dt>
          <dd className="text-slate-700">{item.applicable_scenarios.join(", ") || "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-400">审计运行</dt>
          <dd className="font-mono text-slate-700">{item.audit_run_id ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-400">关联证据</dt>
          <dd className="font-mono text-slate-700">{item.evidence_refs.join(", ") || "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-400">验证说明</dt>
          <dd className="text-slate-700">{item.validation_notes ?? "—"}</dd>
        </div>
      </dl>
    </Card>
  );
}
