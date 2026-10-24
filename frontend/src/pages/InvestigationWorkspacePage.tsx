import { Link, useParams } from "react-router-dom";

import { useInvestigation, useTimeline } from "../hooks/use-investigations";
import { useGraph } from "../hooks/use-graph";
import { useReport } from "../hooks/use-reports";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import { InvestigationTimeline } from "../components/shared/investigation-timeline";
import type { MetaInfo } from "../types/dashboard";
import type { TimelineEvent } from "../types/investigations";
import { cn } from "../utils/cn";

const STATUS_TONE: Record<string, string> = {
  created: "bg-slate-100 text-slate-600",
  pending: "bg-slate-100 text-slate-600",
  planned: "bg-sky-50 text-sky-700",
  running: "bg-brand-50 text-brand-700",
  submitted: "bg-brand-50 text-brand-700",
  completed: "bg-emerald-50 text-emerald-700",
  finished: "bg-emerald-50 text-emerald-700",
  blocked: "bg-amber-50 text-amber-700",
  failed: "bg-red-50 text-red-700",
  unknown: "bg-slate-100 text-slate-500",
  submission_ambiguous: "bg-amber-100 text-amber-800",
};

const SEVERITY_TONE: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-slate-100 text-slate-600",
  unknown: "bg-slate-100 text-slate-500",
};

/**
 * Investigation workspace (B14): status, timeline, graph, risks, evidence and
 * defense candidates for one investigation in a single view. Every panel is
 * driven by real IDs from the investigation detail - no fabricated linkage.
 */
export function InvestigationWorkspacePage() {
  const { requestId = "" } = useParams();
  const detail = useInvestigation(requestId);
  const timeline = useTimeline(requestId);
  const graph = useGraph(requestId);
  const runId = detail.data?.investigation?.run_id ?? "";
  const report = useReport(runId);

  if (detail.isPending) {
    return <PageHeader title="调查工作区" description={`正在加载 ${requestId}…`} />;
  }

  if (detail.isError || !detail.data) {
    return (
      <div className="space-y-4">
        <PageHeader title="调查工作区" description={`请求 ID：${requestId}`} />
        <ErrorState
          title="调查加载失败"
          message={detail.error instanceof Error ? detail.error.message : "未知错误"}
          code={(detail.error as { code?: string }).code}
          requestId={(detail.error as { requestId?: string | null }).requestId}
          onRetry={() => void detail.refetch()}
          retrying={detail.isFetching}
        />
      </div>
    );
  }

  const investigation = detail.data.investigation;
  const meta = detail.data.meta as MetaInfo;
  const timelineMeta = (timeline.data?.meta ?? {}) as Record<string, unknown>;
  const graphData = graph.data?.graph;
  const findings = (report.data?.report?.findings as Array<Record<string, unknown>> | undefined) ?? [];
  const status = String(investigation.status ?? "unknown");

  return (
    <div className="space-y-4">
      <PageHeader
        title="调查工作区"
        description={`${requestId} · ${investigation.mode ?? "—"} · ${investigation.scenario_id ?? ""}`}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => void detail.refetch()}>刷新</Button>
            <Link to={`/investigations/${encodeURIComponent(requestId)}`} className="text-sm text-slate-500 hover:text-slate-700">
              简要详情
            </Link>
          </div>
        }
      />

      <DemoBanner meta={meta} />

      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="neutral" className={cn("font-medium", STATUS_TONE[status] ?? "bg-slate-100 text-slate-600")}>
          {status}
        </Badge>
        {investigation.workflow_status && (
          <span className="font-mono text-xs text-slate-500">workflow: {investigation.workflow_status}</span>
        )}
        <span className="font-mono text-[11px] text-slate-400">
          数据源: {String(meta?.data_mode ?? "—")}
          {timelineMeta.timeline_source === "upstream" ? " · 时间线=上游事件" : ""}
          {timelineMeta.timeline_source === "derived" ? " · 时间线=状态推导" : ""}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card
          title="调查时间线"
          description={
            timelineMeta.timeline_source === "upstream"
              ? "来自 AgentGuard 持久化事件"
              : (timelineMeta.derived_reason as string | undefined) ?? "由已确认字段推导；未确认步骤保持 pending"
          }
        >
          <InvestigationTimeline events={(timeline.data?.events as TimelineEvent[] | undefined) ?? []} />
        </Card>

        <Card
          title="Agent 交互图谱"
          description={
            graphData?.upstream_available === false
              ? "上游报告该工作流暂无消息级元数据（诚实空图谱）"
              : "节点与边来自 AgentGuard 交互图谱接口；候选路径不是已确认因果路径"
          }
          action={
            <Link to={`/interaction-graph?request_id=${encodeURIComponent(requestId)}`} className="text-xs text-brand-700 hover:underline">
              完整图谱 →
            </Link>
          }
        >
          {graph.isError ? (
            <p className="text-xs text-slate-500">
              图谱不可用：{graph.error instanceof Error ? graph.error.message : "未知错误"}
            </p>
          ) : graphData && graphData.nodes.length > 0 ? (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-1.5">
                {graphData.nodes.slice(0, 24).map((node) => (
                  <span key={node.id} className="rounded-md border border-surface-border px-2 py-0.5 font-mono text-[11px] text-slate-700">
                    {node.label}
                    <span className="ml-1 text-[10px] text-slate-400">{node.type}</span>
                  </span>
                ))}
              </div>
              <ul className="space-y-1 text-[11px] text-slate-600">
                {graphData.edges.slice(0, 12).map((edge) => (
                  <li key={edge.id} className="font-mono">
                    {edge.source} → {edge.target}
                    <span className="ml-1 text-slate-400">({edge.type}{edge.message_id ? ` · ${edge.message_id}` : ""})</span>
                  </li>
                ))}
              </ul>
              {graphData.candidate_paths.length > 0 && (
                <p className="text-[11px] text-amber-700">
                  候选路径 {graphData.candidate_paths.length} 条（线索，不是已确认因果路径）
                </p>
              )}
            </div>
          ) : (
            <div className="text-xs text-slate-500">
              <p>当前上游没有可展示的图谱数据。</p>
              <ul className="mt-2 list-inside list-disc text-[11px] text-amber-700">
                {((graphData?.not_provable ?? []) as string[]).map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card
          title="候选风险发现"
          description={runId ? `来自报告 ${runId}` : "调查尚未产生 run_id（preflight blocked 或未提交运行）"}
        >
          {findings.length > 0 ? (
            <ul className="space-y-2 text-xs">
              {findings.map((finding, index) => (
                <li key={String(finding.finding_id ?? index)} className="rounded-md border border-surface-border p-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-slate-700">{String(finding.finding_id ?? "?")}</span>
                    <Badge variant="neutral" className={SEVERITY_TONE[String(finding.severity ?? "unknown")] ?? ""}>
                      {String(finding.severity ?? "unknown")}
                    </Badge>
                    <span className="text-slate-600">{String(finding.risk_type ?? "")}</span>
                  </div>
                  <p className="mt-1 text-slate-600">{String(finding.summary ?? "")}</p>
                  <p className="mt-1 font-mono text-[10px] text-slate-400">
                    证据: {Array.isArray(finding.evidence_ids) ? finding.evidence_ids.join(", ") : "—"}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-slate-500">
              {runId ? "报告未包含风险发现（真实空集）。" : "无 run_id 时不存在报告数据——不伪造风险。"}
            </p>
          )}
        </Card>

        <Card title="证据与防御候选" description="同一调查的证据索引与防御候选入口">
          <div className="space-y-2 text-xs text-slate-600">
            <p>
              <Link to={`/evidence?request_id=${encodeURIComponent(requestId)}`} className="text-brand-700 hover:underline">
                证据分析 →
              </Link>
              <span className="ml-2 text-slate-400">按 request_id 深链，证据等级与验证状态来自 AgentGuard</span>
            </p>
            <p>
              <Link to={`/defenses?request_id=${encodeURIComponent(requestId)}`} className="text-brand-700 hover:underline">
                定向防御 →
              </Link>
              <span className="ml-2 text-slate-400">候选/预览只读；执行能力以 AgentGuard 能力清单为准</span>
            </p>
            {runId && (
              <p>
                <Link to={`/reports/${encodeURIComponent(runId)}`} className="text-brand-700 hover:underline">
                  调查报告 →
                </Link>
                <span className="ml-2 text-slate-400">run {runId}</span>
              </p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
