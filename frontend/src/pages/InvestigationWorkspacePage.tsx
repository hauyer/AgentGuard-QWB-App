import { Link, useParams } from "react-router-dom";
import { useState } from "react";

import { useInvestigation, useTimeline } from "../hooks/use-investigations";
import { useInvestigationLoops } from "../hooks/use-investigation-loops";
import { useGraph } from "../hooks/use-graph";
import { useReport } from "../hooks/use-reports";
import { useLinkInvestigationToProject, useProjects } from "../hooks/use-projects";
import { useAuthStore } from "../stores/auth-store";
import { hasRole } from "../utils/roles";
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
  const loops = useInvestigationLoops(requestId, detail.data?.meta.data_mode === "live");

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

      <InvestigationLoopsPanel requestId={requestId} dataMode={meta.data_mode} query={loops} />

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

      <ProjectLinkPanel requestId={requestId} />
    </div>
  );
}

function InvestigationLoopsPanel({
  requestId,
  dataMode,
  query,
}: {
  requestId: string;
  dataMode: string;
  query: ReturnType<typeof useInvestigationLoops>;
}) {
  if (dataMode !== "live") {
    return (
      <Card title="多轮调查循环" description={`数据源：${dataMode.toUpperCase()}`}>
        <p className="text-xs text-slate-600">
          当前基础调查来自 {dataMode.toUpperCase()} 数据源。只有 Live AgentGuard 列表可验证项目归属并开放真实 Loop 详情；此处不会回退到合成循环。
        </p>
      </Card>
    );
  }

  const response = query.data;
  const canOpenDetails = response?.meta.ownership_verified === true;
  return (
    <Card
      title="多轮调查循环"
      description={canOpenDetails ? "项目归属已由 AgentGuard Live 列表验证" : "Loop 列表由 AgentGuard Live 提供"}
    >
      <p className="mb-3 text-[11px] text-slate-500">
        数据源：{response ? `LIVE · ${response.meta.source ?? "AgentGuard"}` : "LIVE · 正在确认上游来源"}
      </p>
      {query.isPending && <p className="text-xs text-slate-500">正在读取 Loop 列表…</p>}
      {query.isError && (
        <div className="flex items-center justify-between gap-3 text-xs text-red-700">
          <span>{query.error instanceof Error ? query.error.message : "Loop 列表暂不可用"}</span>
          <Button variant="secondary" onClick={() => void query.refetch()}>重试</Button>
        </div>
      )}
      {response && !canOpenDetails && (
        <p className="text-xs text-amber-700">服务端未确认 Loop 项目归属，详情入口已关闭。</p>
      )}
      {response && response.items.length === 0 && canOpenDetails && (
        <p className="text-xs text-slate-500">该基础调查目前没有 AgentGuard Loop。</p>
      )}
      {response && response.items.length > 0 && (
        <ul className="space-y-2">
          {response.items.map((item) => (
            <li key={item.loop_id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-surface-border p-3 text-xs">
              <div className="space-y-1">
                <p className="font-mono text-slate-800">{item.loop_id}</p>
                <p className="text-slate-600">
                  阶段：{item.phase ?? "未提供"} · 策略：{item.strategy ?? "未提供"} · 执行轮次：{item.rounds_executed ?? item.metrics?.rounds_executed ?? "未提供"}
                </p>
                {item.stop_reason && <p className="text-slate-500">停止原因：{item.stop_reason}</p>}
                {item.created_at && <p className="text-[11px] text-slate-400">创建时间：{item.created_at}</p>}
              </div>
              {canOpenDetails ? (
                <Link
                  to={`/investigation-journal?loop_id=${encodeURIComponent(item.loop_id)}`}
                  className="font-medium text-brand-700 hover:underline"
                >
                  查看多轮记录 →
                </Link>
              ) : (
                <span className="text-slate-400">归属待验证</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {!canOpenDetails && !query.isPending && !query.isError && !response && (
        <p className="text-xs text-slate-500">尚无可验证的 Loop 列表。</p>
      )}
      <p className="mt-3 text-[11px] text-slate-400">基础调查：<span className="font-mono">{requestId}</span></p>
    </Card>
  );
}

/** B18: link this investigation to one of the caller's projects (server
 * verifies existence per data mode and audits the operation). */
function ProjectLinkPanel({ requestId }: { requestId: string }) {
  const role = useAuthStore((state) => state.role);
  const canManage = hasRole("analyst", role);
  const projects = useProjects(50, 0);
  const link = useLinkInvestigationToProject();
  const [selectedProject, setSelectedProject] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const activeProjects = (projects.data?.items ?? []).filter((project) => project.status === "active");

  if (!canManage) {
    return (
      <Card title="项目归属" description="viewer 角色只读；关联调查需要 analyst 及以上且为项目成员">
        <p className="text-xs text-slate-500">当前角色无法执行项目关联操作。</p>
      </Card>
    );
  }

  return (
    <Card title="项目归属" description="将本调查引用挂到项目下（服务端验证调查存在并写审计）">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <select
          value={selectedProject}
          onChange={(event) => setSelectedProject(event.target.value)}
          className="w-64 rounded-md border border-surface-border px-2 py-1.5"
        >
          <option value="">选择项目…</option>
          {activeProjects.map((project) => (
            <option key={project.project_id} value={project.project_id}>
              {project.name}
            </option>
          ))}
        </select>
        <Button
          variant="secondary"
          disabled={!selectedProject || link.isPending}
          onClick={() =>
            void (async () => {
              setError(null);
              setMessage(null);
              try {
                await link.mutateAsync({ projectId: Number(selectedProject), requestId });
                setMessage(`已关联到项目（verification 结果见该项目的调查引用列表）`);
              } catch (linkError) {
                setError(linkError instanceof Error ? linkError.message : "关联失败");
              }
            })()
          }
        >
          关联调查
        </Button>
        {message && <span className="text-emerald-700">{message}</span>}
        {error && <span className="text-red-700">{error}</span>}
        {!projects.isLoading && activeProjects.length === 0 && (
          <span className="text-slate-400">暂无可关联的活跃项目（项目管理页可创建）。</span>
        )}
      </div>
    </Card>
  );
}
