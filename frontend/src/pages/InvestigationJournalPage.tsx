import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import type { MetaInfo } from "../types/dashboard";

// AgentGuard E2 真实合同类型
// 对应上游: InvestigationLoopView / LoopDecisionView / LoopDecisionsResponse
// LoopEvidenceChangesResponse / LoopBudgetResponse

type LoopPhase = "CREATED" | "RUNNING" | "BLOCKED" | "COMPLETED" | "FAILED";

interface LoopDetail {
  loop_id: string;
  base_request_id: string;
  phase: LoopPhase;
  strategy: string;
  stop_reason: string | null;
  degradation: string | null;
}

interface LoopDecision {
  round_index: number;
  candidate_actions: string[];
  selected_action_id: string;
  selection_reason: string | null;
  result_status: string;
  new_evidence: boolean;
}

interface LoopEvidenceChanges {
  evidence_refs_before: string[];
  evidence_refs_after: string[];
  new_evidence_count: number;
}

interface LoopBudget {
  budget: { max_actions: number; max_seconds: number; max_model_calls: number };
  metrics: { used_actions: number; actual_seconds: number; model_calls_used: number };
  remaining: { actions_left: number; seconds_left: number; model_calls_left: number };
}

async function fetchLoop(loopId: string, signal?: AbortSignal): Promise<{ meta: MetaInfo } & LoopDetail> {
  const res = await fetch(`/api/investigation-loops/${encodeURIComponent(loopId)}`, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchLoopDecisions(loopId: string, signal?: AbortSignal): Promise<{ meta: MetaInfo; items: LoopDecision[] }> {
  const res = await fetch(`/api/investigation-loops/${encodeURIComponent(loopId)}/decisions`, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchLoopEvidenceChanges(loopId: string, signal?: AbortSignal): Promise<{ meta: MetaInfo } & LoopEvidenceChanges> {
  const res = await fetch(`/api/investigation-loops/${encodeURIComponent(loopId)}/evidence-changes`, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchLoopBudget(loopId: string, signal?: AbortSignal): Promise<{ meta: MetaInfo } & LoopBudget> {
  const res = await fetch(`/api/investigation-loops/${encodeURIComponent(loopId)}/budget`, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

const phaseBadge: Record<LoopPhase, string> = {
  CREATED: "bg-blue-50 text-blue-700",
  RUNNING: "bg-yellow-50 text-yellow-700",
  BLOCKED: "bg-red-50 text-red-700",
  COMPLETED: "bg-green-50 text-green-700",
  FAILED: "bg-red-100 text-red-800",
};

export function InvestigationJournalPage() {
  const [searchParams] = useSearchParams();
  const initialLoopId = searchParams.get("loop_id") ?? "";
  const [loopId, setLoopId] = useState(initialLoopId);

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
  const decisions = decisionsQuery.data?.items ?? [];
  const evidence = evidenceQuery.data;
  const budget = budgetQuery.data;
  const error = loopQuery.error || decisionsQuery.error || budgetQuery.error || evidenceQuery.error;
  const isLoading = loopQuery.isLoading || decisionsQuery.isLoading || budgetQuery.isLoading || evidenceQuery.isLoading;

  return (
    <div className="space-y-4">
      <PageHeader
        title="多轮调查"
        description="AgentGuard E2 多轮自主调查记录。展示每轮动作选择、执行结果、证据变化与预算消耗。"
      />

      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs text-slate-500">Loop ID：</span>
        <input
          value={loopId}
          onChange={(e) => setLoopId(e.target.value)}
          placeholder="输入 loop_id"
          className="rounded-md border border-surface-border px-2 py-1 text-xs font-mono"
        />
      </div>

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
        <p className="text-sm text-slate-400">请输入 loop_id 以查看多轮调查详情。</p>
      )}

      {loop && (
        <>
          <DemoBanner meta={loop.meta} />

          <Card title="Loop 概况">
            <div className="flex flex-wrap items-center gap-4 text-xs">
              <span className="text-slate-600">Loop ID：<span className="font-mono">{loop.loop_id}</span></span>
              <span className="text-slate-600">基础调查：<span className="font-mono">{loop.base_request_id}</span></span>
              <span className="text-slate-600">状态：
                <span className={`ml-1 rounded-full px-2 py-0.5 font-medium ${phaseBadge[loop.phase] ?? "bg-slate-100 text-slate-600"}`}>
                  {loop.phase}
                </span>
              </span>
              <span className="text-slate-600">策略：<Badge variant="ok">{loop.strategy}</Badge></span>
              {loop.stop_reason && <span className="text-slate-600">停止原因：{loop.stop_reason}</span>}
              {loop.degradation && <span className="text-orange-600">降级：{loop.degradation}</span>}
            </div>
          </Card>

          {budget && (
            <Card title="预算消耗">
              <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
                <div>动作：{budget.metrics.used_actions ?? "未提供"}/{budget.budget.max_actions}</div>
                <div>时间：{budget.metrics.actual_seconds ? `${budget.metrics.actual_seconds.toFixed(1)}s` : "未提供"}/{budget.budget.max_seconds}s</div>
                <div>模型调用：{budget.metrics.model_calls_used ?? "未提供"}/{budget.budget.max_model_calls}</div>
              </div>
            </Card>
          )}

          <div className="space-y-3">
            {decisions.map((decision) => (
              <Card key={decision.round_index} title={`Round ${decision.round_index}`}>
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
                </p>
              </Card>
            ))}
          </div>

          {decisions.length === 0 && (
            <p className="text-sm text-slate-400">暂无决策记录。</p>
          )}

          {evidence && (
            <Card title="证据变化">
              <div className="text-xs text-slate-600">
                <p className="mb-1">
                  <span className="font-medium">证据总数：</span>
                  {evidence.new_evidence_count ?? 0} 条新证据
                </p>
                <p className="mb-1">
                  <span className="font-medium">证据引用：</span>
                  {evidence.evidence_refs_after && evidence.evidence_refs_after.length > 0
                    ? evidence.evidence_refs_after.map((id) => (
                        <span key={id} className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 font-mono">{id}</span>
                      ))
                    : "（无）"}
                </p>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
