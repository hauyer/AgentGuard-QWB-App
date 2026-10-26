import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useAuthStore } from "../stores/auth-store";
import { apiGet } from "../services/api";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import type { MetaInfo } from "../types/dashboard";
import { cn } from "../utils/cn";

export interface DemoStep {
  step: number;
  title: string;
  path: string;
  fixture_ref?: string | null;
  description?: string | null;
}

export interface DemoScenario {
  scenario_id: string;
  name?: string | null;
  description?: string | null;
  risk_types?: string[] | null;
}

export interface DemoOverviewResponse {
  meta: MetaInfo;
  flow: DemoStep[];
  scenarios: DemoScenario[];
  scenarios_error?: string | null;
}

function fetchDemoOverview(signal?: AbortSignal): Promise<DemoOverviewResponse> {
  return apiGet<DemoOverviewResponse>("/demo/overview", signal);
}

export function DemoCenterPage() {
  const role = useAuthStore((state) => state.role);
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["demo-overview"],
    queryFn: ({ signal }) => fetchDemoOverview(signal),
  });

  const flow = data?.flow ?? [];
  const scenarios = data?.scenarios ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="演示导览"
        description="可复现的离线流程。数据标记为 RECORDED 或 SYNTHETIC。"
      />

      {isLoading && <p className="text-sm text-slate-400">正在加载演示导览…</p>}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-xs text-red-700">
          演示导览不可用：{error instanceof Error ? error.message : "未知错误"}
          <button
            type="button"
            onClick={() => void refetch()}
            className="ml-3 underline disabled:opacity-50"
            disabled={isFetching}
          >
            重试
          </button>
        </div>
      )}

      {data && (
        <>
          <DemoBanner meta={data.meta} />

          <Card title={`演示场景（${scenarios.length}）`}>
            {scenarios.length === 0 ? (
              <p className="text-sm text-slate-400">
                {data.scenarios_error === "API_UNAVAILABLE"
                  ? "AgentGuard 不可达且未启用演示模式：场景列表不可用，但流程导览仍可浏览。"
                  : "暂无可用场景。"}
              </p>
            ) : (
              <div className="space-y-2">
                {scenarios.map((scenario) => (
                  <div key={scenario.scenario_id} className="rounded-md border border-surface-border p-3 text-xs">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-slate-700">{scenario.scenario_id}</span>
                      <span className="font-medium text-slate-800">{scenario.name ?? "—"}</span>
                      {(scenario.risk_types ?? []).map((risk) => (
                        <Badge key={risk} variant="neutral">
                          {risk}
                        </Badge>
                      ))}
                    </div>
                    {scenario.description && <p className="mt-1 text-slate-600">{scenario.description}</p>}
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="演示流程（9 步）">
            <ol className="space-y-2">
              {flow.map((step) => (
                <li key={step.step} className="flex items-start gap-3 rounded-md border border-surface-border p-3 text-xs">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 font-mono font-semibold text-brand-700">
                    {step.step}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-slate-800">{step.title}</span>
                      {step.fixture_ref && <Badge variant="neutral" className="font-mono">{step.fixture_ref}</Badge>}
                      <Link
                        to={step.path}
                        className={cn(
                          "ml-auto rounded-md px-2 py-0.5 font-medium text-brand-700 hover:bg-brand-50",
                        )}
                      >
                        进入 →
                      </Link>
                    </div>
                    {step.description && <p className="mt-1 text-slate-500">{step.description}</p>}
                  </div>
                </li>
              ))}
            </ol>
          </Card>
        </>
      )}

      <p className="text-[11px] text-slate-400">
        当前角色：<span className="font-mono">{role ?? "未登录"}</span>。录制数据模式不执行虚假的提交或审批操作；
        演示数据不进入 AgentGuard 经验奖励库，不得用于真实因果实验统计。
      </p>
    </div>
  );
}
