import { AlertTriangle, ServerCrash } from "lucide-react";

import { DemoBanner } from "../components/shared/demo-banner";
import { MetricCard } from "../components/shared/metric-card";
import { PageHeader } from "../components/shared/page-header";
import { Skeleton } from "../components/shared/skeleton";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { StatusDot } from "../components/ui/status-dot";
import { useDashboard } from "../hooks/use-dashboard";
import { cn } from "../utils/cn";

export function SystemOverviewPage() {
  const { data, isPending, isError, error, refetch, isFetching } = useDashboard();

  if (isPending) {
    return (
      <div className="space-y-4">
        <PageHeader title="系统总览" description="当前系统运行状态与安全调查概况" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Card key={i} title="…">
              <Skeleton className="h-5 w-20" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="space-y-4">
        <PageHeader title="系统总览" description="当前系统运行状态与安全调查概况" />
        <ErrorState
          kind="backend"
          message={error instanceof Error ? error.message : "无法读取系统状态"}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      </div>
    );
  }

  const { system, meta } = data;

  return (
    <div className="space-y-4">
      <PageHeader title="系统总览" description="当前系统运行状态与安全调查概况" />
      <DemoBanner meta={meta} />

      {/* 系统健康 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <HealthCard title="应用服务 BFF" ok={system.app.status === "ok"} detail={`${system.app.name} v${system.app.version}`} />
        <HealthCard
          title="AgentGuard"
          ok={system.agentguard.reachable}
          detail={
            system.agentguard.health?.version
              ? `v${system.agentguard.health.version} · ${system.agentguard.health.status}`
              : system.agentguard.error?.message ?? "未知"
          }
          errorCode={system.agentguard.error?.code}
          requestId={system.agentguard.error?.request_id}
        />
        <HealthCard
          title="WARDEN 内核"
          ok={system.warden.status === "available"}
          detail={
            system.warden.status === "available"
              ? `可用 · ${system.warden.base_url ?? ""}`
              : system.warden.reason ?? `状态：${system.warden.status}`
          }
          errorCode={system.warden.error_code ?? undefined}
        />
      </div>

      {/* 调查概况 */}
      <Card title="调查概况" description={sampleNote(data.investigation_summary.sample_based, "最近 200 条样本")}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <MetricCard title="调查总数" value={data.investigation_summary.total} unavailable={!data.investigation_summary.available} />
          <MetricCard title="运行中" value={data.investigation_summary.running} unavailable={!data.investigation_summary.available} />
          <MetricCard title="已完成" value={data.investigation_summary.completed} unavailable={!data.investigation_summary.available} />
          <MetricCard title="阻塞" value={data.investigation_summary.blocked} unavailable={!data.investigation_summary.available} />
          <MetricCard title="失败" value={data.investigation_summary.failed} unavailable={!data.investigation_summary.available} />
          <MetricCard title="待处理" value={data.investigation_summary.pending} unavailable={!data.investigation_summary.available} />
        </div>
        {data.investigation_summary.error && (
          <p className="mt-2 text-xs text-red-700">{data.investigation_summary.error}</p>
        )}
        {data.investigation_summary.recent_request_id && (
          <p className="mt-2 font-mono text-[11px] text-slate-500">
            最近一次调查：{data.investigation_summary.recent_request_id}（{data.investigation_summary.recent_status}）
          </p>
        )}
      </Card>

      {/* 风险与证据 */}
      <Card
        title="风险与证据"
        description={sampleNote(data.evidence_summary.sample_based, "最近完成调查的抽样证据")}
      >
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div>
            <h3 className="mb-2 text-xs font-medium text-slate-500">证据等级分布</h3>
            {data.evidence_summary.available ? (
              <ul className="space-y-1.5 text-sm">
                {Object.entries(data.evidence_summary.by_level).map(([level, count]) => (
                  <li key={level} className="flex items-center justify-between">
                    <span className="font-mono text-xs text-slate-600">{level}</span>
                    <span className="font-medium text-slate-800">{count}</span>
                  </li>
                ))}
                {Object.keys(data.evidence_summary.by_level).length === 0 && (
                  <li className="text-xs text-slate-400">无证据数据</li>
                )}
              </ul>
            ) : (
              <Unavailable note={data.evidence_summary.error} />
            )}
          </div>
          <div>
            <h3 className="mb-2 text-xs font-medium text-slate-500">验证状态分布</h3>
            {data.evidence_summary.available ? (
              <ul className="space-y-1.5 text-sm">
                {Object.entries(data.evidence_summary.by_verification).map(([status, count]) => (
                  <li key={status} className="flex items-center justify-between">
                    <span className="font-mono text-xs text-slate-600">{status}</span>
                    <span className="font-medium text-slate-800">{count}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <Unavailable note={data.evidence_summary.error} />
            )}
          </div>
        </div>
        <p className="mt-3 text-[11px] text-slate-400">观测性结果不标注为因果路径已确认。</p>
      </Card>

      {/* 策略状态 */}
      <Card title="策略状态" description="防御候选仅预览，不执行">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricCard title="待审批候选" value={data.policy_summary.pending_approval} unavailable={!data.policy_summary.available} />
          <MetricCard title="已审批候选" value={data.policy_summary.approved} unavailable={!data.policy_summary.available} />
          <MetricCard title="不支持执行" value={data.policy_summary.unsupported} unavailable={!data.policy_summary.available} />
          <MetricCard title="已验证历史结果" value={data.policy_summary.verified_historical} unavailable={!data.policy_summary.available} />
        </div>
        {data.policy_summary.error && <p className="mt-2 text-xs text-red-700">{data.policy_summary.error}</p>}
      </Card>

      {/* 审计能力与依赖阻塞 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="可用审计能力" description="来自 /v1/system/capabilities 的真实清单">
          {data.audit_capabilities.length > 0 ? (
            <ul className="space-y-1.5 text-xs">
              {data.audit_capabilities.map((cap) => (
                <li key={cap.name} className="flex items-center justify-between gap-2">
                  <span className="font-mono text-slate-600">{cap.name}</span>
                  <span className="flex items-center gap-1.5">
                    {cap.note && <span className="text-slate-400">{cap.note}</span>}
                    <StatusDot tone={cap.enabled ? "ok" : "neutral"} />
                    <Badge variant={cap.enabled ? "ok" : "neutral"}>{cap.enabled ? "可用" : "不可用"}</Badge>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">能力清单不可用</p>
          )}
        </Card>

        <Card title="后端依赖阻塞" description="AgentGuard A7 验收期已知集成阻塞">
          <ul className="space-y-2 text-xs">
            {data.dependency_blockers.map((blocker) => (
              <li key={blocker.id} className="flex items-start gap-2">
                <AlertTriangle aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
                <span>
                  <span className="font-mono font-medium text-slate-700">
                    {blocker.id} {blocker.title}
                  </span>
                  <span className="ml-1 text-slate-500">— {blocker.impact}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}

function sampleNote(sampleBased: boolean, label: string): string | undefined {
  return sampleBased ? `基于 ${label}，非全量统计` : undefined;
}

function Unavailable({ note }: { note?: string | null }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-400">
      <ServerCrash aria-hidden className="h-4 w-4" />
      不可用
      {note && <span className="text-xs text-slate-400">（{note}）</span>}
    </div>
  );
}

function HealthCard({
  title,
  ok,
  detail,
  errorCode,
  requestId,
}: {
  title: string;
  ok: boolean;
  detail: string;
  errorCode?: string;
  requestId?: string | null;
}) {
  return (
    <Card title={title}>
      <div className="flex items-center gap-2">
        <StatusDot tone={ok ? "ok" : "danger"} />
        <Badge variant={ok ? "ok" : "danger"}>{ok ? "正常" : "不可用"}</Badge>
      </div>
      <p className={cn("mt-2 text-sm", ok ? "text-slate-600" : "text-red-700")}>{detail}</p>
      {errorCode && (
        <p className="mt-1 font-mono text-xs text-slate-500">
          错误码：{errorCode}
          {requestId && <span className="ml-2">Request ID：{requestId}</span>}
        </p>
      )}
    </Card>
  );
}
