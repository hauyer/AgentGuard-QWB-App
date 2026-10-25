import { useQuery } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";

import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import type { MetaInfo } from "../types/dashboard";

interface StrategyMetric {
  strategy: string;
  time_to_evidence: number;
  evidence_count: number;
  effective_action_ratio: number;
  redundant_actions: number;
  cost_usd: number;
  degradation_rate: number;
  budget_used: number;
  stop_reason: string;
}

interface StrategyComparison {
  scenario_id: string;
  model_version: string;
  seed: number;
  budget: { max_actions: number; max_seconds: number; max_model_calls: number };
  sample_count: number;
  uses_real_llm: boolean;
  is_real_observation: boolean;
  comparability_warnings: string[];
  strategies: StrategyMetric[];
}

async function fetchStrategyComparison(signal?: AbortSignal): Promise<{ meta: MetaInfo } & StrategyComparison> {
  const res = await fetch("/api/experiments/compare", { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function StrategyComparisonPage() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["strategy-comparison"],
    queryFn: ({ signal }) => fetchStrategyComparison(signal),
  });

  const strategies = data?.strategies ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="策略对比"
        description="AgentGuard E3/E4 五策略比较。指标必须追溯到真实实验记录，不可比较的实验明确标注。"
      />

      {isLoading && <p className="text-sm text-slate-400">正在加载策略对比数据…</p>}

      {error && (
        <ErrorState
          title="策略对比不可用"
          message={error instanceof Error ? error.message : "无法获取策略对比数据"}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      )}

      {data && (
        <>
          <DemoBanner meta={data.meta} />

          <Card title="实验条件">
            <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
              <div>场景：<Badge variant="neutral" className="font-mono">{data.scenario_id}</Badge></div>
              <div>模型：<span className="font-mono">{data.model_version}</span></div>
              <div>Seed：{data.seed}</div>
              <div>样本数：{data.sample_count}</div>
              <div>真实 LLM：{data.uses_real_llm ? "是" : "否"}</div>
              <div>真实观察：{data.is_real_observation ? "是" : "否"}</div>
              <div>预算：{data.budget.max_actions} 动作 / {data.budget.max_seconds}s / {data.budget.max_model_calls} 调用</div>
            </div>
            {data.comparability_warnings.length > 0 && (
              <div className="mt-2 rounded border border-yellow-200 bg-yellow-50 px-3 py-2">
                <p className="text-xs font-medium text-yellow-800">可比性警告：</p>
                <ul className="ml-4 list-disc text-xs text-yellow-700">
                  {data.comparability_warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="时间到证据 (秒)">
              <ReactECharts
                option={{
                  tooltip: { trigger: "axis" },
                  xAxis: { type: "category", data: strategies.map((s) => s.strategy) },
                  yAxis: { type: "value", name: "秒" },
                  series: [{ type: "bar", data: strategies.map((s) => s.time_to_evidence), itemStyle: { color: "#3b82f6" } }],
                }}
                style={{ height: 260 }}
              />
            </Card>

            <Card title="证据发现数量">
              <ReactECharts
                option={{
                  tooltip: { trigger: "axis" },
                  xAxis: { type: "category", data: strategies.map((s) => s.strategy) },
                  yAxis: { type: "value" },
                  series: [{ type: "bar", data: strategies.map((s) => s.evidence_count), itemStyle: { color: "#10b981" } }],
                }}
                style={{ height: 260 }}
              />
            </Card>

            <Card title="有效动作比例">
              <ReactECharts
                option={{
                  tooltip: { trigger: "axis" },
                  xAxis: { type: "category", data: strategies.map((s) => s.strategy) },
                  yAxis: { type: "value", max: 1 },
                  series: [{ type: "bar", data: strategies.map((s) => s.effective_action_ratio), itemStyle: { color: "#8b5cf6" } }],
                }}
                style={{ height: 260 }}
              />
            </Card>

            <Card title="调查成本 (USD)">
              <ReactECharts
                option={{
                  tooltip: { trigger: "axis" },
                  xAxis: { type: "category", data: strategies.map((s) => s.strategy) },
                  yAxis: { type: "value", name: "$" },
                  series: [{ type: "bar", data: strategies.map((s) => s.cost_usd), itemStyle: { color: "#f59e0b" } }],
                }}
                style={{ height: 260 }}
              />
            </Card>
          </div>

          <Card title="策略详情">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b text-left text-slate-500">
                    <th className="py-2 pr-4">策略</th>
                    <th className="py-2 pr-4">时间(s)</th>
                    <th className="py-2 pr-4">证据数</th>
                    <th className="py-2 pr-4">有效率</th>
                    <th className="py-2 pr-4">冗余</th>
                    <th className="py-2 pr-4">成本($)</th>
                    <th className="py-2 pr-4">降级率</th>
                    <th className="py-2 pr-4">停止原因</th>
                  </tr>
                </thead>
                <tbody>
                  {strategies.map((s) => (
                    <tr key={s.strategy} className="border-b border-slate-100">
                      <td className="py-2 pr-4 font-mono">{s.strategy}</td>
                      <td className="py-2 pr-4">{s.time_to_evidence.toFixed(1)}</td>
                      <td className="py-2 pr-4">{s.evidence_count}</td>
                      <td className="py-2 pr-4">{(s.effective_action_ratio * 100).toFixed(0)}%</td>
                      <td className="py-2 pr-4">{s.redundant_actions}</td>
                      <td className="py-2 pr-4">{s.cost_usd.toFixed(2)}</td>
                      <td className="py-2 pr-4">{(s.degradation_rate * 100).toFixed(0)}%</td>
                      <td className="py-2 pr-4">{s.stop_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="rounded border border-blue-200 bg-blue-50 px-4 py-3">
            <p className="text-xs text-blue-800">
              <span className="font-medium">防御效果：</span>
              尚无可验证的真实防御效果数据。没有 WARDEN 实际干预和独立评价结果，不生成防御效果曲线。
            </p>
          </div>
        </>
      )}
    </div>
  );
}
