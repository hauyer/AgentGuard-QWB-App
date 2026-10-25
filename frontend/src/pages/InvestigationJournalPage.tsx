import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import type { MetaInfo } from "../types/dashboard";

interface LoopDetail {
  loop_id: string;
  base_request_id: string;
  status: string;
  strategy: string;
  stop_reason: string | null;
  degradation: string | null;
}

interface LoopDecision {
  round: number;
  candidate_actions: { action: string; reason: string; selected: boolean; blocked?: string }[];
  selected_action: string;
  execution_result: string;
  new_evidence: string[];
  budget_used: { actions: number; seconds: number; model_calls: number };
  continue: boolean;
}

interface LoopBudget {
  max_actions: number;
  used_actions: number;
  max_seconds: number;
  actual_seconds: number;
  max_model_calls: number;
  model_calls_used: number;
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

async function fetchLoopBudget(loopId: string, signal?: AbortSignal): Promise<{ meta: MetaInfo } & LoopBudget> {
  const res = await fetch(`/api/investigation-loops/${encodeURIComponent(loopId)}/budget`, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

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

  const budgetQuery = useQuery({
    queryKey: ["loop-budget", loopId],
    queryFn: ({ signal }) => fetchLoopBudget(loopId, signal),
    enabled: !!loopId,
  });

  const loop = loopQuery.data;
  const decisions = decisionsQuery.data?.items ?? [];
  const budget = budgetQuery.data;
  const error = loopQuery.error || decisionsQuery.error || budgetQuery.error;
  const isLoading = loopQuery.isLoading || decisionsQuery.isLoading || budgetQuery.isLoading;

  return (
    <div className="space-y-4">
      <PageHeader
        title="多轮调查"
        description="AgentGuard E6 多轮自主调查记录。展示每轮动作选择、执行结果、证据变化与预算消耗。"
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
          onRetry={() => { loopQuery.refetch(); decisionsQuery.refetch(); budgetQuery.refetch(); }}
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
              <span className="text-slate-600">状态：<Badge variant="neutral">{loop.status}</Badge></span>
              <span className="text-slate-600">策略：<Badge variant="ok">{loop.strategy}</Badge></span>
              {loop.stop_reason && <span className="text-slate-600">停止原因：{loop.stop_reason}</span>}
              {loop.degradation && <span className="text-orange-600">降级：{loop.degradation}</span>}
            </div>
          </Card>

          {budget && (
            <Card title="预算消耗">
              <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
                <div>动作：{budget.used_actions ?? "未提供"}/{budget.max_actions}</div>
                <div>时间：{budget.actual_seconds ? `${budget.actual_seconds.toFixed(1)}s` : "未提供"}/{budget.max_seconds}s</div>
                <div>模型调用：{budget.model_calls_used ?? "未提供"}/{budget.max_model_calls}</div>
              </div>
            </Card>
          )}

          <div className="space-y-3">
            {decisions.map((round) => (
              <Card key={round.round} title={`Round ${round.round}`}>
                <div className="mb-2 flex items-center gap-2 text-xs">
                  <span className="text-slate-500">最终动作：</span>
                  <Badge variant="ok">{round.selected_action}</Badge>
                </div>
                <div className="mb-2 text-xs text-slate-600">
                  <span className="font-medium">候选动作：</span>
                  <ul className="ml-4 mt-1 list-disc">
                    {round.candidate_actions.map((c) => (
                      <li key={c.action}>
                        <span className={c.selected ? "font-medium text-slate-800" : "text-slate-400"}>
                          {c.action}
                        </span>
                        {c.blocked && <span className="ml-2 text-red-600">[{c.blocked}]</span>}
                        <span className="ml-2 text-slate-500">— {c.reason}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <p className="text-xs text-slate-600">
                  <span className="font-medium">执行结果：</span>
                  {round.execution_result}
                </p>
                {round.new_evidence.length > 0 && (
                  <div className="mt-1 text-xs text-slate-600">
                    <span className="font-medium">新增证据：</span>
                    {round.new_evidence.map((id) => (
                      <span key={id} className="ml-2 rounded bg-green-50 px-1.5 py-0.5 font-mono text-green-700">
                        {id}
                      </span>
                    ))}
                  </div>
                )}
                <p className="mt-1 text-xs text-slate-500">
                  本轮消耗：{round.budget_used.actions} 动作 / {round.budget_used.seconds.toFixed(1)}s / {round.budget_used.model_calls} 模型调用
                  {round.continue ? " → 继续下一轮" : " → 停止调查"}
                </p>
              </Card>
            ))}
          </div>

          {decisions.length === 0 && (
            <p className="text-sm text-slate-400">暂无决策记录。</p>
          )}
        </>
      )}
    </div>
  );
}
