import { useState } from "react";

import { useAuthStore } from "../stores/auth-store";
import { useExperiments } from "../hooks/use-reports";
import { useExperimentCompare } from "../hooks/use-reports";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import type { Experiment } from "../types/reports";
import { cn } from "../utils/cn";

interface CompareResult {
  meta?: { data_mode?: string; capability?: string };
  comparable?: boolean;
  reasons?: string[];
  entries?: Array<Record<string, unknown>>;
  comparison?: Record<string, unknown>;
  run_ids?: string[];
}

export function ExperimentsPage() {
  const role = useAuthStore((state) => state.role);
  const { data, isLoading, error, refetch, isFetching } = useExperiments();

  const items = data?.items ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-4">
      <PageHeader
        title="实验对比"
        description="按模型、场景、策略、风险指标和预算比较运行记录。"
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

      <ExperimentComparePanel
        runIds={items.map((item) => item.run_id).filter((value): value is string => Boolean(value))}
      />

      <p className="text-[11px] text-slate-400">
        当前角色：<span className="font-mono">{role ?? "未登录"}</span>。受控对比仅在 Live 模式开放，
        合成实验不与真实证据混入同一统计系列；不可比时展示原因而非伪造提升率。
      </p>
    </div>
  );
}

/** B18: controlled comparison over the B13 backend contract. Incomparable
 * input is answered with explicit reasons - never a fabricated improvement. */
function ExperimentComparePanel({ runIds }: { runIds: string[] }) {
  const compare = useExperimentCompare();
  const [selection, setSelection] = useState<Set<string>>(new Set<string>());

  const toggle = (runId: string) => {
    setSelection((previous) => {
      const next = new Set(previous);
      if (next.has(runId)) next.delete(runId);
      else if (next.size < 20) next.add(runId);
      return next;
    });
  };

  const result = compare.data as CompareResult | undefined;

  return (
    <Card
      title="受控实验对比"
      description="选择 2–20 个 run_id；服务端先验证可比性（同场景、指标可用、证据等级不混合）"
    >
      {runIds.length === 0 ? (
        <p className="text-xs text-slate-500">当前没有可参与对比的 run。</p>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-1.5">
            {runIds.map((runId) => (
              <button
                key={runId}
                type="button"
                onClick={() => toggle(runId)}
                className={cn(
                  "rounded-md border px-2 py-0.5 font-mono text-[11px]",
                  selection.has(runId)
                    ? "border-brand-600 bg-brand-50 text-brand-700"
                    : "border-surface-border text-slate-600 hover:bg-surface-muted",
                )}
              >
                {runId}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              disabled={selection.size < 2 || compare.isPending}
              onClick={() =>
                void compare.mutateAsync({ runIds: [...selection] }).catch(() => undefined)
              }
            >
              {compare.isPending ? "对比中…" : "发起对比"}
            </Button>
            <span className="text-[11px] text-slate-400">已选 {selection.size} 个</span>
          </div>
          {compare.isError && (
            <p className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">
              {compare.error instanceof Error ? compare.error.message : "对比失败"}
            </p>
          )}
          {result && (
            <div className="space-y-2 text-xs">
              {result.comparable === false ? (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-2">
                  <p className="font-medium text-amber-800">不可比，未计算任何提升率：</p>
                  <ul className="mt-1 list-inside list-disc text-amber-700">
                    {(result.reasons ?? []).map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="rounded-md border border-surface-border p-2">
                  <p className="font-medium text-slate-700">
                    对比结果（run_ids: {(result.run_ids ?? []).join(", ")}）
                  </p>
                  <pre className="mt-1 overflow-auto rounded bg-surface-muted p-2 font-mono text-[10px] text-slate-700">
                    {JSON.stringify(result.comparison ?? {}, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
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
