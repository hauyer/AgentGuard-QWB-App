import { Link, useParams } from "react-router-dom";

import { useInvestigation, useTimeline } from "../hooks/use-investigations";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { JsonViewer } from "../components/ui/json-viewer";
import { PageHeader } from "../components/shared/page-header";
import { DemoBanner } from "../components/shared/demo-banner";
import { InvestigationTimeline } from "../components/shared/investigation-timeline";
import type { MetaInfo } from "../types/dashboard";
import type { TimelineEvent } from "../types/investigations";

const STATUS_TONE: Record<string, string> = {
  pending: "bg-slate-100 text-slate-600",
  planned: "bg-sky-50 text-sky-700",
  running: "bg-brand-50 text-brand-700",
  completed: "bg-emerald-50 text-emerald-700",
  blocked: "bg-amber-50 text-amber-700",
  failed: "bg-red-50 text-red-700",
};

/**
 * Investigation detail. The request ID lives in the URL, so refreshing or
 * bookmarking the page always finds the same investigation.
 */
export function InvestigationDetailPage() {
  const { requestId = "" } = useParams();
  const detail = useInvestigation(requestId);
  const timeline = useTimeline(requestId);

  if (detail.isPending) {
    return <PageHeader title="调查详情" description={`正在加载 ${requestId}…`} />;
  }

  if (detail.isError || !detail.data) {
    return (
      <div className="space-y-4">
        <PageHeader
          title="调查详情"
          description="按请求 ID 查询"
          actions={
            <Link to="/investigations" className="text-sm text-slate-500 hover:text-slate-700">
              返回列表
            </Link>
          }
        />
        <ErrorState
          title="调查加载失败"
          message={detail.error instanceof Error ? detail.error.message : "未知错误"}
          code={(detail.error as { code?: string }).code}
          requestId={(detail.error as { requestId?: string | null }).requestId}
          onRetry={() => void detail.refetch()}
          retrying={detail.isFetching}
        />
      </div>
    );
  }

  const investigation = detail.data.investigation;
  const meta = detail.data.meta as MetaInfo;

  return (
    <div className="space-y-4">
      <PageHeader
        title="调查详情"
        description={`${requestId} · ${investigation.mode ?? "—"} · ${investigation.scenario_id ?? ""}`}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => void detail.refetch()}>
              刷新
            </Button>
            <Link to="/investigations" className="text-sm text-slate-500 hover:text-slate-700">
              返回列表
            </Link>
          </div>
        }
      />

      <DemoBanner meta={meta} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="执行状态" className="lg:col-span-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="neutral" className={STATUS_TONE[investigation.status] ?? ""}>
              {investigation.status}
            </Badge>
            {investigation.workflow_status && (
              <span className="font-mono text-xs text-slate-500">workflow: {investigation.workflow_status}</span>
            )}
            {investigation.experiment_id && (
              <span className="font-mono text-xs text-slate-500">实验：{investigation.experiment_id}</span>
            )}
          </div>
          <dl className="mt-4 grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
            <Field label="AgentGuard 请求 ID" value={investigation.request_id} mono />
            <Field label="审计计划" value={investigation.plan_id ?? "—"} mono />
            <Field label="WARDEN 运行 ID" value={investigation.run_id ?? "—"} mono />
            <Field label="模型 / 运行时" value={`${investigation.model_id ?? "—"} / ${investigation.runtime_id ?? "—"}`} />
            <Field label="创建时间" value={investigation.created_at ?? "—"} mono />
            <Field label="更新时间" value={investigation.updated_at ?? "—"} mono />
          </dl>
          {investigation.error_code && (
            <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3">
              <p className="font-mono text-xs text-red-700">
                {investigation.error_code}: {investigation.error_message ?? ""}
              </p>
            </div>
          )}
          {investigation.demo_note && (
            <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs text-amber-800">{investigation.demo_note}</p>
            </div>
          )}
        </Card>

        <Card title="调查时间线" description="仅标记有数据支撑的步骤">
          <InvestigationTimeline events={(timeline.data?.events as TimelineEvent[] | undefined) ?? []} />
        </Card>
      </div>

      {investigation.result !== undefined && investigation.result !== null && (
        <Card title="调查结果">
          <JsonViewer value={investigation.result} />
          {Array.isArray(investigation.follow_up) && investigation.follow_up.length > 0 && (
            <div className="mt-3">
              <h3 className="mb-1 text-xs font-medium text-slate-500">后续调查建议</h3>
              <ul className="list-inside list-disc text-xs text-slate-600">
                {investigation.follow_up.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}

      <div className="flex items-center gap-2">
        {investigation.allows_defense_candidates && (
          <Link to={`/defenses?request_id=${encodeURIComponent(requestId)}`}>
            <Button variant="secondary">查看防御候选</Button>
          </Link>
        )}
        <Link to={`/evidence?request_id=${encodeURIComponent(requestId)}`}>
          <Button variant="secondary">查看证据</Button>
        </Link>
      </div>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-slate-400">{label}</dt>
      <dd className={mono ? "font-mono text-slate-700" : "text-slate-700"}>{value}</dd>
    </div>
  );
}
