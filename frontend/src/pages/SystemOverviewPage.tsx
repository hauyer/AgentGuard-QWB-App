import { AlertTriangle, ServerCrash } from "lucide-react";

import { DemoBanner } from "../components/shared/demo-banner";
import { PageHeader } from "../components/shared/page-header";
import { Skeleton } from "../components/shared/skeleton";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { StatusDot } from "../components/ui/status-dot";
import { useDashboard } from "../hooks/use-dashboard";
import type { LayerStatusSummary } from "../types/system";
import { cn } from "../utils/cn";

export function SystemOverviewPage() {
  const { data, isPending, isError, error, refetch, isFetching } = useDashboard();

  if (isPending) {
    return (
      <div className="space-y-4">
        <PageHeader title="系统与诊断" description="查看服务连接、运行资源、依赖检查与权限设置。" />
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
        <PageHeader title="系统与诊断" description="查看服务连接、运行资源、依赖检查与权限设置。" />
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
      <PageHeader title="系统与诊断" description="查看服务连接、运行资源、依赖检查与权限设置。" />
      <DemoBanner meta={meta} />

      <Card title="依赖状态">
        <div className="grid grid-cols-1 divide-y divide-surface-border sm:grid-cols-2 sm:divide-y-0 xl:grid-cols-4 xl:divide-x">
          <HealthStatus title="应用服务 BFF" ok={system.app.status === "ok"} detail={`${system.app.name} v${system.app.version}`} />
          <HealthStatus
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
          <HealthStatus
            title="WARDEN 内核"
            ok={system.warden.status === "available"}
            detail={
              system.warden.status === "available"
                ? `可用 · ${system.warden.base_url ?? ""}`
                : system.warden.reason ?? `状态：${system.warden.status}`
            }
            errorCode={system.warden.error_code ?? undefined}
          />
          <LayerStatusCard title="模型 / Agent Runtime" summary={system.runtime} />
        </div>
      </Card>

      <Card title="运行能力与资源" description="只显示 AgentGuard 公开报告的状态；未知表示没有对应的可验证状态。">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <LayerStatusCard title="Probe / SAE" summary={system.probe_sae} />
          <LayerStatusCard title="威胁合同" summary={system.threat_contracts} />
          <LayerStatusCard title="证据工件" summary={system.artifacts} />
        </div>
      </Card>

      <details className="system-audit-history"><summary>通用审计历史概况 · 调查、证据与策略统计</summary><p className="mt-3 text-xs text-slate-500">以下来自通用审计索引；研究的真实通信与配对效果请在结果分析台核验。</p><div className="space-y-4 pt-4">
      {/* 调查概况 */}
      <Card title="调查概况" description={sampleNote(data.investigation_summary.sample_based, "最近 200 条样本")}>
        <MetricStrip
          unavailable={!data.investigation_summary.available}
          items={[
            { title: "调查总数", value: data.investigation_summary.total },
            { title: "运行中", value: data.investigation_summary.running },
            { title: "已完成", value: data.investigation_summary.completed },
            { title: "阻塞", value: data.investigation_summary.blocked },
            { title: "失败", value: data.investigation_summary.failed },
            { title: "待处理", value: data.investigation_summary.pending },
          ]}
        />
        {data.investigation_summary.error && (
          <p className="mt-2 text-xs text-red-700">{data.investigation_summary.error}</p>
        )}
        {data.investigation_summary.recent_request_id && (
          <p className="mt-2 break-all font-mono text-[11px] text-slate-500">
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
        <MetricStrip
          unavailable={!data.policy_summary.available}
          items={[
            { title: "待审批候选", value: data.policy_summary.pending_approval },
            { title: "已审批候选", value: data.policy_summary.approved },
            { title: "不支持执行", value: data.policy_summary.unsupported },
            { title: "已验证历史结果", value: data.policy_summary.verified_historical },
          ]}
        />
        {data.policy_summary.error && <p className="mt-2 text-xs text-red-700">{data.policy_summary.error}</p>}
      </Card>

      </div></details>

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

        <Card title="后端依赖阻塞" description="当前固定版本的集成状态">
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

function HealthStatus({
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
    <section className="px-0 py-3 first:pt-0 last:pb-0 sm:px-4 sm:first:pl-0 sm:first:pt-0 sm:last:pr-0 sm:last:pb-0">
      <h3 className="mb-2 text-xs font-semibold text-slate-600">{title}</h3>
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
    </section>
  );
}

function LayerStatusCard({
  title,
  summary,
}: {
  title: string;
  summary?: LayerStatusSummary;
}) {
  const status = summary?.status ?? "unknown";
  const presentation: Record<string, { label: string; variant: "ok" | "warn" | "danger" | "neutral" }> = {
    available: { label: "可用", variant: "ok" },
    blocked: { label: "阻塞", variant: "warn" },
    unavailable: { label: "不可用", variant: "danger" },
    unsupported: { label: "不支持", variant: "neutral" },
    unknown: { label: "未知", variant: "neutral" },
  };
  const current = presentation[status] ?? presentation.unknown;
  return (
    <section className="rounded-md border border-surface-border px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-slate-600">{title}</h3>
        <Badge variant={current.variant}>{current.label}</Badge>
      </div>
      <p className="mt-2 min-h-5 text-sm text-slate-600">
        {summary?.reason ?? summary?.blockers?.join("; ") ??
          (status === "available" ? "AgentGuard 报告可用" : "没有可验证的状态报告")}
      </p>
      <p className="mt-1 text-[11px] text-slate-400">
        责任层：AgentGuard{summary?.source ? ` · 来源：${summary.source}` : " · 来源状态未知"}
      </p>
    </section>
  );
}

function MetricStrip({
  items,
  unavailable,
}: {
  items: { title: string; value: number | null | undefined }[];
  unavailable: boolean;
}) {
  return (
    <dl className="grid grid-cols-2 gap-x-3 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
      {items.map((item) => (
        <div key={item.title} className="border-l border-surface-border pl-3">
          <dt className="text-[11px] text-slate-500">{item.title}</dt>
          <dd className="mt-1 text-lg font-semibold tabular-nums text-slate-800">
            {unavailable || item.value == null ? "不可用" : item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
