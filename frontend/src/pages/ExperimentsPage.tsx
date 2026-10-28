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

      <Card
        title="四层干预研究能力"
        description="按当前固定的 AgentGuard OpenAPI 合同显示能力门控；不把离线快照当作真实运行结果。"
      >
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Badge variant="info">STATIC_ONLY</Badge>
          <span className="text-slate-600">上游已发布 Study 元数据与 run 级配对路由；App 尚未开放。</span>
        </div>
        <p className="mt-2 max-w-4xl text-xs leading-5 text-slate-500">
          AgentGuard 1.1.0rc3 的 86 路径合同只将版本字段从 rc2 更新到 rc3。Study 注册没有上游幂等键，
          注册 Schema 未定义 Track/Arm，分析接口接收的数值数组和工件引用也未独立验证来源；
          run 级配对接口没有与 Study/Arm 绑定。
          这些接口尚未完成真实服务联调或项目授权映射，不能作为已验证的四层研究工作流。
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span className="inline-flex items-center gap-1.5 rounded-md border border-surface-border px-2 py-1 text-slate-600">
            真实 HTTP / 研究运行 <Badge variant="neutral">NOT_RUN</Badge>
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-md border border-surface-border px-2 py-1 text-slate-600">
            上游 WARDEN Live Gate <Badge variant="danger">BLOCKED</Badge>
          </span>
        </div>
        <p className="mt-2 text-[11px] text-slate-400">
          当前没有经核验的 Study、Arm 或效应数据，因此不显示实验矩阵、SRR / BER / U 指标或因果结论。
          WARDEN 状态取自 AgentGuard RC3 I5 门控记录，不代表当前服务探测。
        </p>
      </Card>

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
        {item.metrics_available === true && item.risk_indicators
          ? JSON.stringify(item.risk_indicators)
          : item.metrics_available === false ? "指标不可用" : "未知"}
      </td>
      <td className="py-2 pr-3">
        {item.metrics_available === true && item.utility?.normal_task_success_rate != null
          ? (item.utility.normal_task_success_rate * 100).toFixed(0) + "%"
          : item.metrics_available === false ? "指标不可用" : "未知"}
      </td>
      <td className="py-2 pr-3 font-mono text-[11px]">
        {item.budget ? `${item.budget.tokens ?? "?"} / ${item.budget.time_seconds ?? "?"}s` : "—"}
      </td>
      <td className="py-2 font-mono text-[10px] text-slate-400">
        {item.data_source ?? item.result_source ?? "—"}
        {item.evidence_level && <div>证据：{item.evidence_level}</div>}
      </td>
    </tr>
  );
}
