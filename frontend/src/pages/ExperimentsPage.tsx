import { useAuthStore } from "../stores/auth-store";
import { useExperiments } from "../hooks/use-reports";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import type { Experiment } from "../types/reports";

export function ExperimentsPage() {
  const role = useAuthStore((state) => state.role);
  const { data, isLoading, error, refetch, isFetching } = useExperiments();

  const items = data?.items ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-4">
      <PageHeader
        title="实验对比"
        description="比较维度：模型版本 / 场景 / 调查策略 / 防御策略 / 执行状态 / 风险指标 / 正常任务效用 / 调查预算。"
      />

      {isLoading && <p className="text-sm text-slate-400">正在加载实验数据…</p>}

      {error && (
        <ErrorState
          title="实验对比不可用"
          message={error instanceof Error ? error.message : "无法获取实验数据"}
          code={(error as { code?: string }).code}
          requestId={(error as { requestId?: string | null }).requestId}
          onRetry={() => void refetch()}
          retrying={isFetching}
        />
      )}

      {data && meta && <DemoBanner meta={meta} />}

      {data && items.length > 0 && (
        <Card title={`实验记录（${items.length}）`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] border-collapse text-xs">
              <thead>
                <tr className="border-b border-surface-border text-left text-slate-400">
                  <th className="py-2 pr-3 font-medium">实验</th>
                  <th className="py-2 pr-3 font-medium">模型</th>
                  <th className="py-2 pr-3 font-medium">调查策略</th>
                  <th className="py-2 pr-3 font-medium">防御策略</th>
                  <th className="py-2 pr-3 font-medium">状态</th>
                  <th className="py-2 pr-3 font-medium">风险指标</th>
                  <th className="py-2 pr-3 font-medium">正常任务效用</th>
                  <th className="py-2 pr-3 font-medium">预算（tokens/s）</th>
                  <th className="py-2 font-medium">结果来源</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <ExperimentRow key={item.experiment_id} item={item} />
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-[11px] text-slate-400">
            比较数据均来自可验证的实验报告；无数据时不生成趋势图。
          </p>
        </Card>
      )}

      {data && items.length === 0 && !error && (
        <Card title="实验对比">
          <p className="text-sm text-slate-400">当前没有可验证的实验记录，因此不生成趋势图。</p>
        </Card>
      )}

      <p className="text-[11px] text-slate-400">
        当前角色：<span className="font-mono">{role ?? "未登录"}</span>。Live 模式下 AgentGuard 公共 API 未提供
        实验对比列表（EXPERIMENTS_UNAVAILABLE），不会用虚构数据生成趋势。
      </p>
    </div>
  );
}

function ExperimentRow({ item }: { item: Experiment }) {
  return (
    <tr className="border-b border-surface-border/60 text-slate-700">
      <td className="py-2 pr-3">
        <span className="font-mono">{item.experiment_id}</span>
        <div className="font-mono text-[10px] text-slate-400">{item.scenario_id ?? "—"}</div>
      </td>
      <td className="py-2 pr-3">{item.model_version ?? "—"}</td>
      <td className="py-2 pr-3">{item.investigation_strategy ?? "—"}</td>
      <td className="py-2 pr-3">{item.defense_strategy ?? "—"}</td>
      <td className="py-2 pr-3">
        <Badge variant="neutral">{item.execution_status ?? "—"}</Badge>
      </td>
      <td className="py-2 pr-3 font-mono text-[11px]">
        {item.risk_indicators ? JSON.stringify(item.risk_indicators) : "—"}
      </td>
      <td className="py-2 pr-3">
        {item.utility?.normal_task_success_rate != null
          ? (item.utility.normal_task_success_rate * 100).toFixed(0) + "%"
          : "—"}
      </td>
      <td className="py-2 pr-3 font-mono text-[11px]">
        {item.budget ? `${item.budget.tokens ?? "?"} / ${item.budget.time_seconds ?? "?"}s` : "—"}
      </td>
      <td className="py-2 font-mono text-[10px] text-slate-400">{item.result_source ?? "—"}</td>
    </tr>
  );
}
