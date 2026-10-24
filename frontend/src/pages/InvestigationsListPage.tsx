import { Link, useSearchParams } from "react-router-dom";

import { useAuthStore } from "../stores/auth-store";
import { useInvestigations } from "../hooks/use-investigations";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import { DataTable, type Column } from "../components/shared/data-table";
import { hasRole } from "../utils/roles";
import type { InvestigationSummaryRow } from "../types/investigations";
import { cn } from "../utils/cn";

const STATUS_OPTIONS = [
  { value: "", label: "全部" },
  { value: "pending", label: "待处理" },
  { value: "planned", label: "已计划" },
  { value: "running", label: "运行中" },
  { value: "completed", label: "已完成" },
  { value: "blocked", label: "阻塞" },
  { value: "failed", label: "失败" },
] as const;

const STATUS_TONE: Record<string, string> = {
  pending: "bg-slate-100 text-slate-600",
  planned: "bg-sky-50 text-sky-700",
  running: "bg-brand-50 text-brand-700",
  completed: "bg-emerald-50 text-emerald-700",
  blocked: "bg-amber-50 text-amber-700",
  failed: "bg-red-50 text-red-700",
};

export function InvestigationsListPage() {
  const role = useAuthStore((state) => state.role);
  const canCreate = hasRole("analyst", role);

  // Filter + pagination state lives in the URL so a refresh restores the view.
  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get("status") ?? "";
  const offset = Number(searchParams.get("offset") ?? "0") || 0;
  const limit = 10;

  const { data, isLoading, error, isFetching } = useInvestigations(status, limit, offset);

  const setParam = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams);
    if (value) params.set(key, value);
    else params.delete(key);
    if (key === "status") params.delete("offset");
    setSearchParams(params);
  };

  const columns: Column<InvestigationSummaryRow>[] = [
    {
      key: "request_id",
      header: "调查 ID",
      render: (row) => (
        <Link
          to={`/investigations/${encodeURIComponent(row.request_id)}`}
          className="font-mono text-xs text-brand-700 hover:underline"
        >
          {row.request_id}
        </Link>
      ),
    },
    {
      key: "scenario",
      header: "场景",
      render: (row) => <span className="font-mono text-xs text-slate-600">{row.scenario_id ?? "—"}</span>,
    },
    {
      key: "mode",
      header: "审计模式",
      render: (row) => <span className="text-xs text-slate-600">{row.mode ?? "—"}</span>,
    },
    {
      key: "created",
      header: "创建时间",
      render: (row) => (
        <span className="font-mono text-[11px] text-slate-500">
          {row.created_at?.slice(0, 19).replace("T", " ") ?? "—"}
        </span>
      ),
    },
    {
      key: "status",
      header: "状态",
      render: (row) => (
        <Badge variant="neutral" className={cn("font-medium", STATUS_TONE[row.status] ?? "bg-slate-100 text-slate-600")}>
          {row.status}
        </Badge>
      ),
    },
    {
      key: "run",
      header: "WARDEN 运行",
      render: (row) => (
        <span className="font-mono text-[11px] text-slate-500">
          {row.run_id ? row.run_id : row.error_code ? row.error_code : "—"}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="安全调查"
        description="创建与跟踪多智能体安全审计调查。所有状态来自 AgentGuard 或明确标注的演示样例。"
        actions={
          canCreate ? (
            <Link to="/investigations/new">
              <Button>新建调查</Button>
            </Link>
          ) : undefined
        }
      />

      {data?.meta && <DemoBanner meta={data.meta} />}

      <div className="flex flex-wrap items-center gap-2">
        {STATUS_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setParam("status", option.value)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs",
              status === option.value
                ? "border-brand-600 bg-brand-50 text-brand-700"
                : "border-surface-border text-slate-600 hover:bg-surface-muted",
            )}
          >
            {option.label}
          </button>
        ))}
        {isFetching && !isLoading && <span className="text-xs text-slate-400">刷新中…</span>}
      </div>

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(row) => row.request_id}
        loading={isLoading}
        emptyTitle="没有调查记录"
        emptyDescription={status ? "当前状态下没有调查记录，请切换筛选条件。" : "还没有任何调查，点击「新建调查」开始。"}
        error={
          error ? (
            <ErrorState
              title="调查列表加载失败"
              message={error instanceof Error ? error.message : "未知错误"}
              code={(error as { code?: string }).code}
              requestId={(error as { requestId?: string | null }).requestId}
            />
          ) : undefined
        }
        offset={offset}
        limit={limit}
        count={data?.count ?? 0}
        total={data?.total ?? null}
        nextOffset={data?.next_offset ?? null}
        onPage={(next) => setParam("offset", String(next))}
      />
    </div>
  );
}
