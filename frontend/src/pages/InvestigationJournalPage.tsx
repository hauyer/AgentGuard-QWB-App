import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import type { MetaInfo } from "../types/dashboard";

const SAMPLE_RUN_IDS = ["run-qwb-0001"];

interface Round {
  round: number;
  status: string;
  candidate_actions: { action: string; reason: string; selected: boolean; blocked?: string }[];
  selected_action: string;
  execution_result: string;
  new_evidence: string[];
  budget_used: { actions: number; seconds: number; model_calls: number };
  continue: boolean;
  degradation: string | null;
}

interface InvestigationJournal {
  run_id: string;
  status: string;
  strategy: string;
  budget: { max_actions: number; used_actions: number; max_seconds: number; actual_seconds: number; max_model_calls: number; model_calls_used: number };
  stop_reason: string;
  rounds: Round[];
  evidence_before: string[];
  evidence_final: string[];
}

async function fetchInvestigation(runId: string, signal?: AbortSignal): Promise<{ meta: MetaInfo } & InvestigationJournal> {
  const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/investigation`, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function InvestigationJournalPage() {
  const [searchParams] = useSearchParams();
  const initialRunId = searchParams.get("run_id") ?? SAMPLE_RUN_IDS[0];
  const [runId, setRunId] = useState(initialRunId);
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["investigation-journal", runId],
    queryFn: ({ signal }) => fetchInvestigation(runId, signal),
  });

  const meta = data?.meta;

  return (
    <div className="space-y-4">
      <PageHeader
        title="多轮调查"
        description="AgentGuard E2 多轮自主调查记录。展示每轮动作选择、执行结果、证据变化与预算消耗。"
      />

      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs text-slate-500">运行：</span>
        <select
          value={runId}
          onChange={(event) => setRunId(event.target.value)}
          className="rounded-md border border-surface-border px-2 py-1 text-xs"
        >
          {SAMPLE_RUN_IDS.map((id) => (
            <option key={id} value={id}>{id}</option>
          ))}
        </select>
      </div>

      {isLoading && <p className="text-sm text-slate-400">正在加载多轮调查记录…</p>}

      {error && (
        <ErrorState
          title="多轮调查不可用"
          message={error instanceof Error ? error.message : "无法获取多轮调查数据"}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      )}

      {meta && <DemoBanner meta={meta} />}

      {data && (
        <>
          <Card title="调查概况">
            <div className="flex flex-wrap items-center gap-4 text-xs">
              <span className="text-slate-600">状态：<Badge variant="neutral">{data.status}</Badge></span>
              <span className="text-slate-600">策略：<Badge variant="ok">{data.strategy}</Badge></span>
              <span className="text-slate-600">停止原因：{data.stop_reason}</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
              <div>动作：{data.budget.used_actions}/{data.budget.max_actions}</div>
              <div>时间：{data.budget.actual_seconds.toFixed(1)}s/{data.budget.max_seconds}s</div>
              <div>模型调用：{data.budget.model_calls_used}/{data.budget.max_model_calls}</div>
            </div>
          </Card>

          <div className="space-y-3">
            {data.rounds.map((round) => (
              <Card key={round.round} title={`Round ${round.round}`}>
                <div className="mb-2 flex items-center gap-2 text-xs">
                  <span className="text-slate-500">状态：</span>
                  <Badge variant="neutral">{round.status}</Badge>
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
                {round.degradation && (
                  <p className="mt-1 text-xs text-orange-600">降级：{round.degradation}</p>
                )}
              </Card>
            ))}
          </div>

          <Card title="证据变化">
            <div className="text-xs text-slate-600">
              <p className="mb-1"><span className="font-medium">调查前证据：</span>{data.evidence_before.length === 0 ? "（无）" : data.evidence_before.join(", ")}</p>
              <p><span className="font-medium">最终证据集合：</span>
                {data.evidence_final.map((id) => (
                  <span key={id} className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 font-mono">{id}</span>
                ))}
              </p>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
