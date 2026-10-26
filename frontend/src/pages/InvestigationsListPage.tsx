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
  const keyword = searchParams.get("q") ?? "";
  const offset = Number(searchParams.get("offset") ?? "0") || 0;
  const limit = 10;

  const { data, isLoading, error, isFetching } = useInvestigations(status, limit, offset);

  const setParam = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams);
    if (value) params.set(key, value);
    else params.delete(key);
    if (key !== "offset") params.delete("offset");
    setSearchParams(params);
  };

  // Keyword filter is client-side over the loaded page: request_id / scenario
  // substring match. Server-side search capability is not published upstream.
  const rows = (data?.items ?? []).filter((row) => {
    if (!keyword) return true;
    const needle = keyword.toLowerCase();
    return (
      row.request_id.toLowerCase().includes(needle) ||
      (row.scenario_id ?? "").toLowerCase().includes(needle) ||
      (row.run_id ?? "").toLowerCase().includes(needle)
    );
  });

  const columns: Column<InvestigationSummaryRow>[] = [
    {
      key: "request_id",
      header: "调查 ID",
      render: (row) => (
        <div className="flex flex-col gap-0.5">
          <Link
            to={`/investigations/${encodeURIComponent(row.request_id)}/workspace`}
            className="font-mono text-xs text-brand-700 hover:underline"
          >
            {row.request_id}
          </Link>
          <Link
            to={`/investigations/${encodeURIComponent(row.request_id)}`}
            className="text-[10px] text-slate-400 hover:text-slate-600"
          >
            简要详情
          </Link>
        </div>
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
        description="创建并跟踪项目授权范围内的安全调查。"
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
        <input
          type="search"
          value={keyword}
          onChange={(event) => setParam("q", event.target.value)}
          placeholder="搜索 ID / 场景 / run…"
          className="w-56 rounded-md border border-surface-border px-2 py-1 text-xs"
        />
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
        rows={rows}
        rowKey={(row) => row.request_id}
        loading={isLoading}
        emptyTitle="没有调查记录"
        emptyDescription={
          keyword ? "没有匹配关键字的调查，请调整搜索词。" :
          status ? "当前状态下没有调查记录，请切换筛选条件。" : "还没有任何调查，点击「新建调查」开始。"
        }
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
