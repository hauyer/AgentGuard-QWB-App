import { ServerCrash } from "lucide-react";

import { useSystemStatus } from "../hooks/use-system-status";
import type { SystemStatus } from "../types/system";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { StatusDot } from "../components/ui/status-dot";
import { cn } from "../utils/cn";

function modeVariant(mode: SystemStatus["data_mode"]): "ok" | "warn" | "danger" | "neutral" {
  switch (mode) {
    case "live":
      return "ok";
    case "recorded":
    case "synthetic":
      return "warn";
    case "unavailable":
      return "danger";
  }
}

function modeLabel(mode: SystemStatus["data_mode"]): string {
  return mode.toUpperCase();
}

export function SystemOverviewPage() {
  const { data, isPending, isError, error, refetch, isFetching } = useSystemStatus();

  if (isPending) {
    return (
      <div className="space-y-4">
        <PageTitle />
        <Card title="系统状态" description="正在从 BFF 读取连接状态…">
          <div className="space-y-2">
            <SkeletonLine />
            <SkeletonLine />
            <SkeletonLine />
          </div>
        </Card>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="space-y-4">
        <PageTitle />
        <Card title="后端不可用" description="BFF 无法连接，未展示任何虚构数据">
          <div className="flex flex-col items-start gap-3">
            <div className="flex items-center gap-2 text-red-700">
              <ServerCrash className="h-5 w-5" />
              <span className="text-sm font-medium">
                {error instanceof Error ? error.message : "无法读取系统状态"}
              </span>
            </div>
            <button
              type="button"
              onClick={() => void refetch()}
              disabled={isFetching}
              className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:bg-slate-300"
            >
              {isFetching ? "重试中…" : "重试"}
            </button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageTitle />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <HealthCard
          title="应用服务 BFF"
          ok={data.app.status === "ok"}
          detail={`${data.app.name} v${data.app.version}`}
        />
        <HealthCard
          title="AgentGuard"
          ok={data.agentguard.reachable}
          detail={
            data.agentguard.health?.version
              ? `v${data.agentguard.health.version} · ${data.agentguard.health.status}`
              : data.agentguard.error?.message ?? "未知"
          }
          errorCode={data.agentguard.error?.code}
          requestId={data.agentguard.error?.request_id}
        />
        <HealthCard
          title="WARDEN 内核"
          ok={data.warden.status === "available"}
          detail={
            data.warden.status === "available"
              ? `可用 · ${data.warden.base_url ?? ""}`
              : data.warden.reason ?? `状态：${data.warden.status}`
          }
          errorCode={data.warden.error_code ?? undefined}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="数据模式" description="所有数据必须有明确来源">
          <div className="flex items-center gap-2">
            <Badge variant={modeVariant(data.data_mode)}>{modeLabel(data.data_mode)}</Badge>
            <span className="text-xs text-slate-500">
              {data.data_mode === "live"
                ? "当前响应直接来自 AgentGuard"
                : data.data_mode === "unavailable"
                  ? "当前无法取得所需数据"
                  : "教学或演示数据"}
            </span>
          </div>
        </Card>

        <Card title="AgentGuard 能力" description="来自 /v1/system/capabilities 的真实清单">
          {data.capabilities ? (
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-slate-500">后端模式</span>
                <Badge variant={data.capabilities.backend_mode === "real" ? "ok" : "warn"}>
                  {data.capabilities.backend_mode ?? "unknown"}
                </Badge>
              </div>
              {Object.entries(data.capabilities.capabilities ?? {}).map(([name, enabled]) => (
                <div key={name} className="flex items-center justify-between text-xs">
                  <span className="font-mono text-slate-600">{name}</span>
                  <StatusDot tone={enabled ? "ok" : "neutral"} />
                </div>
              ))}
              {data.capabilities.limitations?.map((limitation) => (
                <p key={limitation} className="text-xs text-amber-700">
                  {limitation}
                </p>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">能力清单不可用</p>
          )}
        </Card>

        <Card title="功能可用性" description="按 AgentGuard 公共接口逐项核对">
          <ul className="space-y-1.5 text-xs">
            {data.features.map((feature) => (
              <li key={feature.name} className="flex items-start justify-between gap-2">
                <span className="font-mono text-slate-600">{feature.name}</span>
                <span className="flex items-center gap-1.5">
                  {feature.reason && !feature.available && (
                    <span className="max-w-[220px] truncate text-slate-400" title={feature.reason}>
                      {feature.reason}
                    </span>
                  )}
                  <Badge variant={feature.available ? "ok" : "danger"}>
                    {feature.available ? "可用" : "不可用"}
                  </Badge>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}

function PageTitle() {
  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-800">系统总览</h1>
      <p className="text-sm text-slate-500">当前系统运行状态与安全调查概况</p>
    </div>
  );
}

function HealthCard({
  title,
  ok,
  detail,
  errorCode,
  requestId,
}: {
  title: string;
  ok: boolean;
  detail: string;
  errorCode?: string;
  requestId?: string | null;
}) {
  return (
    <Card title={title}>
      <div className="flex items-center gap-2">
        <StatusDot tone={ok ? "ok" : "danger"} />
        <Badge variant={ok ? "ok" : "danger"}>{ok ? "正常" : "不可用"}</Badge>
      </div>
      <p className={cn("mt-2 text-sm", ok ? "text-slate-600" : "text-red-700")}>{detail}</p>
      {errorCode && (
        <p className="mt-1 font-mono text-xs text-slate-500">
          错误码：{errorCode}
          {requestId && <span className="ml-2">Request ID：{requestId}</span>}
        </p>
      )}
    </Card>
  );
}

function SkeletonLine() {
  return <div className="h-3.5 w-full animate-pulse rounded bg-surface-muted" />;
}
