import { useResourceSelection } from "../hooks/use-resource-selection";
import { ResourcePicker } from "../components/shared/resource-picker";

import { useAuthStore } from "../stores/auth-store";
import { useDefense, useDefenseOutcomes, usePreviewDefense } from "../hooks/use-evidence";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import { PermissionGate } from "../components/shared/permission-gate";
import { hasRole } from "../utils/roles";
import type { DefenseCandidate } from "../types/evidence";
import { cn } from "../utils/cn";


export function DefensePage() {
  const role = useAuthStore((state) => state.role);
  const [requestId, setRequestId] = useResourceSelection("request_id");
  const { data, isLoading, error, refetch, isFetching } = useDefense(requestId);
  const { data: outcomesData } = useDefenseOutcomes();
  const preview = usePreviewDefense(requestId);

  const defense = data?.defense;
  const meta = data?.meta;
  const canMutate = hasRole("analyst", role);

  return (
    <div className="space-y-4">
      <PageHeader
        title="定向防御"
        description="防御候选仅可预览；执行器尚未通过验证。"
      />

      <ResourcePicker value={requestId} onSelect={setRequestId} kind="investigation"/>
      <PermissionGate required="analyst"><Button variant="secondary" disabled={!requestId||!canMutate||preview.isPending}
        onClick={()=>preview.mutate()}>{preview.isPending?"预览中…":"生成/更新候选预览"}</Button></PermissionGate>

      {isLoading && <p className="text-sm text-slate-400">正在加载防御候选…</p>}

      {error && (
        <ErrorState
          title="防御候选不可用"
          message={error instanceof Error ? error.message : "无法获取防御候选"}
          code={(error as { code?: string }).code}
          requestId={(error as { requestId?: string | null }).requestId}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      )}

      {preview.error && (
        <ErrorState
          title="预览未生成"
          message={preview.error instanceof Error ? preview.error.message : "预览请求失败"}
          code={(preview.error as { code?: string }).code}
          onRetry={() => preview.mutate()}
          retrying={preview.isPending}
        />
      )}

      {data && meta && <DemoBanner meta={meta} />}

      {defense && (
        <>
          <Card title={`调查 ${requestId} 防御状态`}>
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
              <span>
                状态：<Badge variant="neutral">{defense.status ?? "—"}</Badge>
              </span>
              <span>
                运行 ID：<span className="font-mono">{defense.run_id ?? "—"}</span>
              </span>
              <span>
                execution_performed：
                <Badge variant={defense.execution_performed ? "danger" : "neutral"}>
                  {String(defense.execution_performed)}
                </Badge>
              </span>
              <span>
                证据模式：<Badge variant="neutral">{defense.evidence_mode ?? "—"}</Badge>
              </span>
            </div>
            {defense.policy_notes.map((note) => (
              <p key={note} className="mt-2 text-xs text-amber-700">
                ⚠ {note}
              </p>
            ))}
          </Card>

          <div className="space-y-3">
            {defense.candidates.map((candidate) => (
              <CandidateCard key={candidate.candidate_id} candidate={candidate} />
            ))}
            {defense.candidates.length === 0 && (
              <p className="text-sm text-slate-400">该调查尚无防御候选。</p>
            )}
          </div>
        </>
      )}

      {outcomesData && (
        <Card title="已验证的历史防御结果">
          {outcomesData.outcomes.length === 0 ? (
            <p className="text-sm text-slate-400">
              {outcomesData.meta?.data_mode === "live"
                ? "AgentGuard 公共 API 未提供历史防御结果（不虚构数据）。"
                : "暂无历史防御结果。"}
            </p>
          ) : (
            <div className="space-y-2">
              {outcomesData.outcomes.map((outcome) => (
                <div key={outcome.outcome_id} className="rounded-md border border-surface-border p-3 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-slate-700">{outcome.outcome_id}</span>
                    <Badge variant="neutral">{outcome.status ?? "—"}</Badge>
                    <span className="text-slate-400">{outcome.policy ?? "—"} · {outcome.operation_type ?? "—"}</span>
                    <span className="ml-auto font-mono text-slate-400">{outcome.verified_at ?? ""}</span>
                  </div>
                  {outcome.note && <p className="mt-1 text-slate-600">{outcome.note}</p>}
                  {outcome.source && <p className="mt-1 font-mono text-[10px] text-slate-400">source: {outcome.source}</p>}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <p className="text-[11px] text-slate-400">
        当前角色：<span className="font-mono">{role ?? "未登录"}</span>。应用层不开放实际防御执行按钮；
        演示模式不执行虚假的提交或审批操作。
      </p>
    </div>
  );
}

function CandidateCard({ candidate }: { candidate: DefenseCandidate }) {
  return (
    <Card title={candidate.candidate_id}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="neutral">{candidate.risk ?? "—"}</Badge>
        <Badge variant="neutral">操作：{candidate.operation_type ?? "—"}</Badge>
        <Badge variant="neutral">状态：{candidate.status ?? "—"}</Badge>
        <ExecutionBadge supported={candidate.execution_supported} />
      </div>

      <dl className="mt-3 grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
        <Detail label="目标" value={candidate.target ?? "—"} mono wide />
        <Detail label="推荐理由" value={candidate.rationale ?? "—"} wide />
        <Detail label="权限要求" value={candidate.authorization_required ?? "—"} />
        <Detail
          label="预计成本"
          value={
            candidate.estimated_cost
              ? `${candidate.estimated_cost.tokens ?? "?"} tokens / ${candidate.estimated_cost.time_seconds ?? "?"}s`
              : "—"
          }
        />
        <Detail label="相关证据" value={candidate.related_evidence.join(", ") || "—"} mono wide />
      </dl>

      {candidate.execution_reason && (
        <p className="mt-3 rounded-md bg-surface-muted p-2 text-xs text-slate-600">{candidate.execution_reason}</p>
      )}
    </Card>
  );
}

function ExecutionBadge({ supported }: { supported: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset",
        supported ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20" : "bg-slate-100 text-slate-500 ring-slate-500/20",
      )}
    >
      {supported ? "可执行" : "UNSUPPORTED"}
    </span>
  );
}

function Detail({ label, value, mono, wide }: { label: string; value: string; mono?: boolean; wide?: boolean }) {
  return (
    <div className={wide ? "sm:col-span-2" : undefined}>
      <dt className="text-slate-400">{label}</dt>
      <dd className={mono ? "font-mono text-slate-700" : "text-slate-700"}>{value}</dd>
    </div>
  );
}
