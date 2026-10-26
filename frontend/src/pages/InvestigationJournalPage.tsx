import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import type { MetaInfo } from "../types/dashboard";
import { apiGet } from "../services/api";

// AgentGuard E2 官方合同类型
// 对应上游: InvestigationLoopView / LoopDecisionView / LoopDecisionsResponse
// LoopEvidenceChangesResponse / LoopBudgetResponse

type LoopPhase = string;

interface LoopDetail {
  loop_id: string;
  base_request_id: string;
  phase: LoopPhase;
  strategy: string;
  stop_reason: string | null;
  degradation: string | null;
}

interface LoopDecision {
  decision_id: string;
  round_index: number;
  phase: LoopPhase;
  strategy: string;
  candidate_actions: string[];
  selected_action_id: string;
  selection_reason: string | null;
  evidence_refs: string[];
  evidence_refs_before: string[];
  evidence_refs_after: string[];
  new_evidence_count: number;
  cost_estimate: number | null;
  actual_cost: number | null;
  remaining_budget: number | null;
  result_status: string;
  new_evidence: boolean;
  stop_reason: string | null;
}

interface LoopEvidenceChangesResponse {
  schema_version: string;
  loop_id: string;
  items: LoopDecision[];
  count: number;
  limitations: string[];
}

interface LoopBudget {
  loop_id: string;
  budget: { max_actions: number; max_seconds: number; max_model_calls: number };
  metrics: {
    rounds_executed: number;
    elapsed_seconds: number;
    model_calls_used: number;
    steps_to_first_evidence: number | null;
    effective_action_ratio: number | null;
  };
  remaining: {
    actions_left: number;
    seconds_left: number;
    model_calls_left: number;
  };
}

async function fetchLoop(loopId: string, signal?: AbortSignal): Promise<{ meta: MetaInfo } & LoopDetail> {
  return apiGet<{ meta: MetaInfo } & LoopDetail>(`/investigation-loops/${encodeURIComponent(loopId)}`, signal);
}

async function fetchLoopDecisions(loopId: string, signal?: AbortSignal): Promise<{ meta: MetaInfo; items: LoopDecision[] }> {
  return apiGet<{ meta: MetaInfo; items: LoopDecision[] }>(`/investigation-loops/${encodeURIComponent(loopId)}/decisions`, signal);
}

async function fetchLoopEvidenceChanges(loopId: string, signal?: AbortSignal): Promise<{ meta: MetaInfo } & LoopEvidenceChangesResponse> {
  return apiGet<{ meta: MetaInfo } & LoopEvidenceChangesResponse>(`/investigation-loops/${encodeURIComponent(loopId)}/evidence-changes`, signal);
}

async function fetchLoopBudget(loopId: string, signal?: AbortSignal): Promise<{ meta: MetaInfo } & LoopBudget> {
  return apiGet<{ meta: MetaInfo } & LoopBudget>(`/investigation-loops/${encodeURIComponent(loopId)}/budget`, signal);
}

function phaseBadge(phase: LoopPhase) {
  const map: Record<string, string> = {
    CREATED: "bg-blue-50 text-blue-700",
    RUNNING: "bg-yellow-50 text-yellow-700",
    BLOCKED: "bg-red-50 text-red-700",
    COMPLETED: "bg-green-50 text-green-700",
    STOPPED: "bg-orange-50 text-orange-700",
    FAILED: "bg-red-100 text-red-800",
  };
  return map[phase] ?? "bg-slate-100 text-slate-600";
}

export function InvestigationJournalPage() {
  const [searchParams] = useSearchParams();
  const loopId = searchParams.get("loop_id") ?? "";
  const [pollState, setPollState] = useState({ loopId: "", count: 0 });

  const loopQuery = useQuery({
    queryKey: ["loop", loopId],
    queryFn: ({ signal }) => fetchLoop(loopId, signal),
    enabled: !!loopId,
  });

  const decisionsQuery = useQuery({
    queryKey: ["loop-decisions", loopId],
    queryFn: ({ signal }) => fetchLoopDecisions(loopId, signal),
    enabled: !!loopId,
  });

  const evidenceQuery = useQuery({
    queryKey: ["loop-evidence", loopId],
    queryFn: ({ signal }) => fetchLoopEvidenceChanges(loopId, signal),
    enabled: !!loopId,
  });

  const budgetQuery = useQuery({
    queryKey: ["loop-budget", loopId],
    queryFn: ({ signal }) => fetchLoopBudget(loopId, signal),
    enabled: !!loopId,
  });

  const loop = loopQuery.data;
  const phase = String(loop?.phase ?? "").toUpperCase();
  const pollCount = pollState.loopId === loopId ? pollState.count : 0;
  const refetchLoop = loopQuery.refetch;
  const decisions = decisionsQuery.data?.items ?? [];
  const evidence = evidenceQuery.data;
  const budget = budgetQuery.data;
  const error = loopQuery.error || decisionsQuery.error || budgetQuery.error || evidenceQuery.error;
  const isLoading = loopQuery.isLoading || decisionsQuery.isLoading || budgetQuery.isLoading || evidenceQuery.isLoading;

  useEffect(() => {
    if (!loopId || !["CREATED", "RUNNING"].includes(phase) || pollCount >= 20) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void refetchLoop().finally(() => {
        if (!cancelled) setPollState({ loopId, count: pollCount + 1 });
      });
    }, 3000);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [loopId, phase, pollCount, refetchLoop]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="多轮调查"
        description="按轮查看决策、证据变化和预算消耗。"
        actions={
          loop?.base_request_id ? (
            <Link
              to={`/investigations/${encodeURIComponent(loop.base_request_id)}/workspace`}
              className="text-sm text-brand-700 hover:underline"
            >
              返回基础调查工作区
            </Link>
          ) : (
            <Link to="/investigations" className="text-sm text-brand-700 hover:underline">
              选择项目调查
            </Link>
          )
        }
      />

      {isLoading && loopId && <p className="text-sm text-slate-400">正在加载多轮调查…</p>}

      {error && (
        <ErrorState
          title="多轮调查不可用"
          message={error instanceof Error ? error.message : "无法获取多轮调查数据"}
          onRetry={() => {
            loopQuery.refetch(); decisionsQuery.refetch();
            budgetQuery.refetch(); evidenceQuery.refetch();
          }}
          retrying={loopQuery.isFetching}
        />
      )}

      {!loopId && (
        <Card title="从项目调查进入多轮记录">
          <p className="text-sm text-slate-600">打开一个项目关联的基础调查，在已验证的 Loop 列表中选择记录。页面不接受手动 loop_id 输入。</p>
          <Link to="/projects" className="mt-2 inline-block text-sm text-brand-700 hover:underline">前往项目列表 →</Link>
        </Card>
      )}

      {loop && (
        <>
          <DemoBanner meta={loop.meta} />

          <Card title="Loop 概况">
            <div className="flex flex-wrap items-center gap-4 text-xs">
              <span className="text-slate-500">数据源：{String(loop.meta.data_mode).toUpperCase()}</span>
              <span className="text-slate-600">Loop ID：<span className="font-mono">{loop.loop_id}</span></span>
              <span className="text-slate-600">基础调查：<span className="font-mono">{loop.base_request_id}</span></span>
              <span className="text-slate-600">状态：
                <span className={`ml-1 rounded-full px-2 py-0.5 font-medium ${phaseBadge(loop.phase)}`}>
                  {loop.phase}
                </span>
              </span>
              <span className="text-slate-600">策略：<Badge variant="ok">{loop.strategy}</Badge></span>
              {loop.stop_reason && <span className="text-slate-600">停止原因：{loop.stop_reason}</span>}
              {loop.degradation && <span className="text-orange-600">降级：{loop.degradation}</span>}
            </div>
          </Card>

          {!["CREATED", "RUNNING"].includes(phase) ? null : pollCount < 20 ? (
            <p className="text-[11px] text-slate-400">Loop 运行中：每 3 秒检查一次，最多 20 次；离开页面会取消轮询。</p>
          ) : (
            <div className="flex items-center gap-2 text-[11px] text-slate-500">
              <span>已停止自动轮询，可手动刷新。</span>
              <button type="button" onClick={() => void refetchLoop()} className="text-brand-700 hover:underline">刷新状态</button>
            </div>
          )}

          {budget && (
            <Card title="预算消耗">
              <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
                <div>执行轮次：{budget.metrics.rounds_executed ?? "未提供"}</div>
                <div>已用时间：{budget.metrics.elapsed_seconds != null ? `${budget.metrics.elapsed_seconds.toFixed(1)}s` : "未提供"}/{budget.budget.max_seconds}s</div>
                <div>模型调用：{budget.metrics.model_calls_used ?? "未提供"}/{budget.budget.max_model_calls}</div>
                <div>首证据步数：{budget.metrics.steps_to_first_evidence ?? "未提供"}</div>
                <div>有效动作率：{budget.metrics.effective_action_ratio != null ? `${(budget.metrics.effective_action_ratio * 100).toFixed(1)}%` : "未提供"}</div>
              </div>
            </Card>
          )}

          <div className="space-y-3">
            {decisions.map((decision) => (
              <Card key={decision.decision_id} title={`Round ${decision.round_index}`}>
                <div className="mb-2 flex items-center gap-2 text-xs">
                  <span className="text-slate-500">最终动作：</span>
                  <Badge variant="ok">{decision.selected_action_id}</Badge>
                </div>
                <div className="mb-2 text-xs text-slate-600">
                  <span className="font-medium">候选动作：</span>
                  <ul className="ml-4 mt-1 list-disc">
                    {decision.candidate_actions.map((action) => (
                      <li key={action} className={action === decision.selected_action_id ? "font-medium text-slate-800" : "text-slate-400"}>
                        {action}
                      </li>
                    ))}
                  </ul>
                </div>
                {decision.selection_reason && (
                  <p className="text-xs text-slate-600">
                    <span className="font-medium">选择理由：</span>
                    {decision.selection_reason}
                  </p>
                )}
                <p className="text-xs text-slate-600">
                  <span className="font-medium">结果状态：</span>
                  {decision.result_status}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  本轮是否产生新证据：{decision.new_evidence ? "是" : "否"}
                  {decision.new_evidence_count != null && `（${decision.new_evidence_count} 条）`}
                </p>
              </Card>
            ))}
          </div>

          {decisions.length === 0 && (
            <p className="text-sm text-slate-400">暂无决策记录。</p>
          )}

          {evidence && (
            <Card title="证据变化">
              {evidence.count === 0 ? (
                <p className="text-xs text-slate-500">暂无新增证据。</p>
              ) : (
                <div className="space-y-2">
                  <p className="text-xs text-slate-600">
                    <span className="font-medium">证据变化总数：</span>
                    {evidence.count}
                  </p>
                  {evidence.items.map((item) => (
                    <div key={item.decision_id} className="text-xs text-slate-600">
                      <span className="font-medium">Round {item.round_index}：</span>
                      {item.new_evidence_count != null && `${item.new_evidence_count} 条新证据`}
                      {item.evidence_refs_after && item.evidence_refs_after.length > 0 && (
                        <span className="ml-2">
                          证据引用：
                          {item.evidence_refs_after.map((id) => (
                            <span key={id} className="ml-1 rounded bg-slate-100 px-1.5 py-0.5 font-mono">{id}</span>
                          ))}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  );
}
