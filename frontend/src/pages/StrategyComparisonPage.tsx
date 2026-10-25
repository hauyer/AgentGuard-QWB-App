import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import {
  fetchStrategyEvaluation,
  fetchStrategyEvaluations,
  type StrategyEvaluation,
  type StrategyEvaluationRun,
} from "../services/research";

function value(value: number | string | null | undefined, digits = 2, suffix = ""): string {
  if (typeof value === "number") {
    return Number.isFinite(value) ? `${value.toFixed(digits)}${suffix}` : "未提供";
  }
  return typeof value === "string" && value.length > 0 ? value : "未提供";
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "未提供";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function RunRow({ run }: { run: StrategyEvaluationRun }) {
  return (
    <tr className="border-b border-slate-100" data-testid="strategy-evaluation-run">
      <td className="py-2 pr-3 font-mono">{run.strategy}</td>
      <td className="py-2 pr-3">{run.repetition}</td>
      <td className="py-2 pr-3">{run.execution_status}</td>
      <td className="py-2 pr-3">{value(run.rounds_executed, 0)}</td>
      <td className="py-2 pr-3">{value(run.steps_to_first_evidence, 0, " 步")}</td>
      <td className="py-2 pr-3">{value(run.elapsed_seconds, 2, " 秒")}</td>
      <td className="py-2 pr-3">{run.strategy_degraded ? "是" : "否"}</td>
      <td className="py-2 pr-3">{value(run.stop_reason)}</td>
    </tr>
  );
}

function EvaluationView({ evaluation }: { evaluation: StrategyEvaluation }) {
  return (
    <div className="space-y-4" data-testid="strategy-evaluation-detail">
      <Card title="评价信息">
        <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div><dt className="text-slate-500">比较 ID</dt><dd className="break-all font-mono">{evaluation.comparison_id}</dd></div>
          <div><dt className="text-slate-500">数据分区</dt><dd>{evaluation.data_partition}</dd></div>
          <div><dt className="text-slate-500">源代码提交</dt><dd className="break-all font-mono">{value(evaluation.source_commit)}</dd></div>
          <div><dt className="text-slate-500">执行时间</dt><dd>{formatTimestamp(evaluation.executed_at)}</dd></div>
          <div><dt className="text-slate-500">案例数</dt><dd>{evaluation.base_request_ids.length}</dd></div>
          <div><dt className="text-slate-500">重复次数</dt><dd>{value(evaluation.repetitions, 0)}</dd></div>
          <div><dt className="text-slate-500">运行记录数</dt><dd>{evaluation.runs.length}</dd></div>
          <div><dt className="text-slate-500">报告工件</dt><dd className="break-all font-mono">{value(evaluation.report_artifact_id)}</dd></div>
        </dl>
        <div className="mt-4">
          <p className="mb-1 text-xs text-slate-500">策略</p>
          <div className="flex flex-wrap gap-2">
            {evaluation.strategies.map((strategy) => (
              <span key={strategy} className="rounded bg-slate-100 px-2 py-1 font-mono text-xs">{strategy}</span>
            ))}
          </div>
        </div>
      </Card>

      <Card title="策略汇总">
        {evaluation.aggregates.length === 0 ? (
          <p className="text-sm text-slate-500">上游未提供汇总记录。</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px] text-xs">
              <thead><tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-3">策略</th><th className="py-2 pr-3">重复次数</th>
                <th className="py-2 pr-3">完成 / 阻塞</th><th className="py-2 pr-3">平均轮数</th>
                <th className="py-2 pr-3">首次证据步数</th><th className="py-2 pr-3">平均耗时</th>
                <th className="py-2 pr-3">有效动作比例</th><th className="py-2 pr-3">降级率</th>
                <th className="py-2 pr-3">平均证据引用</th><th className="py-2">平均冗余动作</th>
              </tr></thead>
              <tbody>{evaluation.aggregates.map((item) => (
                <tr key={item.strategy} className="border-b border-slate-100">
                  <td className="py-2 pr-3 font-mono">{item.strategy}</td>
                  <td className="py-2 pr-3">{value(item.repetitions, 0)}</td>
                  <td className="py-2 pr-3">{value(item.completed_runs, 0)} / {value(item.blocked_runs, 0)}</td>
                  <td className="py-2 pr-3">{value(item.mean_rounds)}</td>
                  <td className="py-2 pr-3">{value(item.mean_steps_to_first_evidence, 2, " 步")}</td>
                  <td className="py-2 pr-3">{value(item.mean_elapsed_seconds, 2, " 秒")}</td>
                  <td className="py-2 pr-3">{item.mean_effective_action_ratio == null ? "未提供" : value(item.mean_effective_action_ratio * 100, 1, "%")}</td>
                  <td className="py-2 pr-3">{item.degradation_rate == null ? "未提供" : value(item.degradation_rate * 100, 1, "%")}</td>
                  <td className="py-2 pr-3">{value(item.mean_evidence_refs)}</td>
                  <td className="py-2">{value(item.mean_redundant_actions)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
        {evaluation.aggregates.some((item) => item.notes.length > 0) && (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-slate-500">
            {evaluation.aggregates.flatMap((item) => item.notes).map((note, index) => <li key={`${index}-${note}`}>{note}</li>)}
          </ul>
        )}
      </Card>

      <Card title="运行记录">
        {evaluation.runs.length === 0 ? (
          <p className="text-sm text-slate-500">上游未提供运行记录。</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px] text-xs">
              <thead><tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-3">策略</th><th className="py-2 pr-3">重复序号</th>
                <th className="py-2 pr-3">状态</th><th className="py-2 pr-3">执行轮数</th>
                <th className="py-2 pr-3">首次证据</th><th className="py-2 pr-3">耗时</th>
                <th className="py-2 pr-3">策略降级</th><th className="py-2 pr-3">停止原因</th>
              </tr></thead>
              <tbody>{evaluation.runs.map((run, index) => (
                <RunRow key={`${run.experiment_id}-${run.run_label}-${index}`} run={run} />
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="案例与限制">
        <p className="mb-2 text-xs text-slate-500">基础调查 ID</p>
        {evaluation.base_request_ids.length > 0 ? (
          <ul className="mb-4 list-disc space-y-1 pl-5 text-xs">
            {evaluation.base_request_ids.map((id) => <li key={id} className="break-all font-mono">{id}</li>)}
          </ul>
        ) : <p className="mb-4 text-xs text-slate-500">未提供</p>}
        <p className="mb-2 text-xs text-slate-500">评价限制</p>
        {evaluation.limitations.length > 0 ? (
          <ul className="list-disc space-y-1 pl-5 text-xs text-slate-600">
            {evaluation.limitations.map((item) => <li key={item}>{item}</li>)}
          </ul>
        ) : <p className="text-xs text-slate-500">上游未提供限制说明。</p>}
        <p className="mt-4 text-xs text-slate-500">
          风险识别与防御效果指标按上游合同保留为空；本页不推断真实 LLM 调用、防御成功率或美元成本。
        </p>
      </Card>
    </div>
  );
}

export function StrategyComparisonPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const listQuery = useQuery({
    queryKey: ["strategy-evaluations"],
    queryFn: ({ signal }) => fetchStrategyEvaluations(signal),
  });
  const items = useMemo(() => listQuery.data?.items ?? [], [listQuery.data?.items]);
  const requestedId = searchParams.get("evaluation_id");
  const selectedId = requestedId ?? items[0]?.evaluation_id ?? "";

  useEffect(() => {
    if (!requestedId && items[0]?.evaluation_id) {
      setSearchParams({ evaluation_id: items[0].evaluation_id }, { replace: true });
    }
  }, [items, requestedId, setSearchParams]);

  const detailQuery = useQuery({
    queryKey: ["strategy-evaluation", selectedId],
    queryFn: ({ signal }) => fetchStrategyEvaluation(selectedId, signal),
    enabled: Boolean(selectedId),
  });

  return (
    <div className="space-y-4">
      <PageHeader
        title="策略评价"
        description="读取 AgentGuard 已持久化的策略评价及其运行明细。页面不触发实验，也不补算上游未提供的指标。"
      />

      {listQuery.isLoading && <p className="text-sm text-slate-400">正在加载策略评价索引…</p>}
      {listQuery.error && (
        <ErrorState title="策略评价不可用" message={listQuery.error instanceof Error ? listQuery.error.message : "无法获取评价索引"}
          onRetry={() => void listQuery.refetch()} retrying={listQuery.isFetching} />
      )}

      {listQuery.data && (
        <Card title="已保存的评价">
          <label htmlFor="strategy-evaluation-select" className="mb-2 block text-xs text-slate-500">选择评价</label>
          <select
            id="strategy-evaluation-select"
            data-testid="strategy-evaluation-select"
            className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm"
            value={selectedId}
            onChange={(event) => setSearchParams(event.target.value ? { evaluation_id: event.target.value } : {})}
          >
            {selectedId && !items.some((item) => item.evaluation_id === selectedId) && (
              <option value={selectedId}>{selectedId}</option>
            )}
            {items.map((item) => (
              <option key={item.evaluation_id} value={item.evaluation_id}>
                {item.comparison_id} · {item.data_partition} · {item.evaluation_id}
              </option>
            ))}
          </select>
          <p className="mt-2 text-xs text-slate-500">{listQuery.data.meta.source_note}</p>
          {items.length === 0 && <p className="mt-3 text-sm text-slate-500">当前没有已保存的策略评价。</p>}
        </Card>
      )}

      {selectedId && detailQuery.isLoading && <p className="text-sm text-slate-400">正在加载评价详情…</p>}
      {selectedId && detailQuery.error && (
        <ErrorState title="评价详情不可用" message={detailQuery.error instanceof Error ? detailQuery.error.message : "无法获取评价详情"}
          onRetry={() => void detailQuery.refetch()} retrying={detailQuery.isFetching} />
      )}
      {detailQuery.data && <EvaluationView evaluation={detailQuery.data.evaluation} />}
    </div>
  );
}
