import { Link, useNavigate, useParams } from "react-router-dom";
import { useEffect, useState } from "react";

import { useInvestigation, useTimeline } from "../hooks/use-investigations";
import {
  useCreateInvestigationLoop,
  useInvestigationLoopSubmission,
  useReconcileInvestigationLoop,
} from "../hooks/use-investigation-loops";
import type { CreateInvestigationLoopRequest, LoopDataPartition, LoopStrategy } from "../services/investigations";
import { useAuthStore } from "../stores/auth-store";
import { ApiError } from "../services/api";
import { hasRole } from "../utils/roles";
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

      <LoopCreatePanel
        requestId={requestId}
        dataMode={meta.data_mode}
        hasProject={((meta as MetaInfo & { project_ids?: number[] }).project_ids ?? []).length > 0}
      />
    </div>
  );
}

interface LoopDraft extends CreateInvestigationLoopRequest {
  pending: boolean;
}

function newLoopDraft(): LoopDraft {
  const fallbackUuid = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const value = Math.floor(Math.random() * 16);
    return (char === "x" ? value : (value & 0x3) | 0x8).toString(16);
  });
  return {
    submission_id: globalThis.crypto?.randomUUID?.() ?? fallbackUuid,
    strategy: "information_value",
    max_actions: 8,
    max_seconds: 300,
    max_model_calls: 4,
    no_new_evidence_rounds: 2,
    data_partition: "held_out_family",
    authorization_ref: "",
    pending: false,
  };
}

function readLoopDraft(key: string): LoopDraft {
  try {
    const raw = window.sessionStorage.getItem(key);
    if (raw) {
      const saved = JSON.parse(raw) as LoopDraft;
      if (saved.submission_id && saved.pending) return saved;
    }
  } catch {
    // Storage can be disabled by browser policy; the request still works in memory.
  }
  return newLoopDraft();
}

function LoopCreatePanel({
  requestId,
  dataMode,
  hasProject,
}: {
  requestId: string;
  dataMode: string;
  hasProject: boolean;
}) {
  const role = useAuthStore((state) => state.role);
  const navigate = useNavigate();
  const canOperate = hasRole("operator", role);
  const storageKey = `qwb.loop-create.${requestId}`;
  const [draft, setDraft] = useState<LoopDraft>(() => readLoopDraft(storageKey));
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const create = useCreateInvestigationLoop(requestId);
  const reconcile = useReconcileInvestigationLoop(requestId);
  const submission = useInvestigationLoopSubmission(requestId, draft.submission_id, draft.pending);

  useEffect(() => {
    if (submission.data?.submission.status === "COMPLETED" && submission.data.submission.loop_id) {
      window.sessionStorage.removeItem(storageKey);
      navigate(`/investigation-journal?loop_id=${encodeURIComponent(submission.data.submission.loop_id)}`);
    }
  }, [navigate, storageKey, submission.data]);

  if (dataMode !== "live") {
    return (
      <Card title="创建多轮调查" description="Live Operator 操作">
        <p className="text-xs text-slate-600">当前调查数据源为 {dataMode}。Demo、Recorded 与 Synthetic 数据不会调用真实 Operator API。</p>
      </Card>
    );
  }
  if (!hasProject) {
    return (
      <Card title="创建多轮调查" description="项目授权检查">
        <p className="text-xs text-slate-600">此调查没有唯一且已验证的 Live 项目归属，不能创建 Loop。</p>
      </Card>
    );
  }
  if (!canOperate) {
    return (
      <Card title="创建多轮调查" description="需要平台 Operator 角色及项目内 Operator 权限">
        <p className="text-xs text-slate-600">当前账号没有 Loop 创建权限。</p>
      </Card>
    );
  }

  const serverStatus = submission.data?.submission;
  const terminal = serverStatus?.status === "FAILED" || serverStatus?.status === "COMPLETED";
  const isUnresolved = draft.pending && !terminal;
  const notFound = submission.error instanceof ApiError && submission.error.code === "SUBMISSION_NOT_FOUND";
  const setField = <K extends keyof CreateInvestigationLoopRequest>(key: K, value: CreateInvestigationLoopRequest[K]) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };
  const clearPending = () => {
    try {
      window.sessionStorage.removeItem(storageKey);
    } catch {
      // The form can still reset when session storage is unavailable.
    }
    setDraft(newLoopDraft());
    setErrorMessage(null);
  };
  const requestBody = (value: LoopDraft): CreateInvestigationLoopRequest => ({
    submission_id: value.submission_id,
    strategy: value.strategy,
    max_actions: value.max_actions,
    max_seconds: value.max_seconds,
    max_model_calls: value.max_model_calls,
    no_new_evidence_rounds: value.no_new_evidence_rounds,
    data_partition: value.data_partition,
    authorization_ref: value.authorization_ref,
  });
  const send = async () => {
    const pendingDraft = { ...draft, pending: true };
    setDraft(pendingDraft);
    try {
      window.sessionStorage.setItem(storageKey, JSON.stringify(pendingDraft));
    } catch {
      // The server remains authoritative; the correlation id stays in memory.
    }
    setErrorMessage(null);
    try {
      const response = await create.mutateAsync(requestBody(pendingDraft));
      if (response.submission.status === "COMPLETED" && response.submission.loop_id) {
        window.sessionStorage.removeItem(storageKey);
        navigate(`/investigation-journal?loop_id=${encodeURIComponent(response.submission.loop_id)}`);
      } else {
        setErrorMessage(response.submission.error?.message ?? "提交状态仍需核对。请稍后检查同一提交。");
        void submission.refetch();
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Loop 创建失败");
      void submission.refetch();
    }
  };
  const checkStatus = async () => {
    setErrorMessage(null);
    try {
      const response = await reconcile.mutateAsync(draft.submission_id);
      if (response.submission.status === "COMPLETED" && response.submission.loop_id) {
        window.sessionStorage.removeItem(storageKey);
        navigate(`/investigation-journal?loop_id=${encodeURIComponent(response.submission.loop_id)}`);
      } else {
        setErrorMessage(response.submission.error?.message ?? "结果尚未唯一确认。请勿创建新的提交。");
        void submission.refetch();
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "暂时无法恢复提交状态");
      void submission.refetch();
    }
  };
  const numericField = (
    label: string,
    key: "max_actions" | "max_seconds" | "max_model_calls" | "no_new_evidence_rounds",
    min: number,
    max: number,
  ) => (
    <label className="flex flex-col gap-1 text-xs text-slate-600">
      {label}
      <input
        type="number"
        min={min}
        max={max}
        value={draft[key]}
        disabled={isUnresolved || create.isPending}
        onChange={(event) => setField(key, Number(event.target.value))}
        className="w-full rounded-md border border-surface-border px-2 py-1.5 text-slate-800"
      />
    </label>
  );

  return (
    <Card title="创建多轮调查" description="需要当前项目授权和 AgentGuard Operator。提交状态与恢复记录保存在服务端。">
      {draft.pending && serverStatus && (
        <div className="mb-3 rounded-md border border-surface-border bg-slate-50 p-3 text-xs">
          <p>提交状态：<strong>{serverStatus.status}</strong>{serverStatus.loop_id ? ` · Loop ${serverStatus.loop_id}` : ""}</p>
          {serverStatus.error && <p className="mt-1 text-amber-800">{serverStatus.error.code}：{serverStatus.error.message}</p>}
        </div>
      )}
      {draft.pending && notFound && (
        <p className="mb-3 text-xs text-slate-500">服务端尚未登记此提交。可能是前置校验未通过；请检查错误原因后再开始新的提交。</p>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1 text-xs text-slate-600">
          策略
          <select
            value={draft.strategy}
            disabled={isUnresolved || create.isPending}
            onChange={(event) => setField("strategy", event.target.value as LoopStrategy)}
            className="rounded-md border border-surface-border px-2 py-1.5 text-slate-800"
          >
            <option value="fixed_order">fixed_order</option>
            <option value="risk_score">risk_score</option>
            <option value="information_value">information_value</option>
            <option value="experience">experience</option>
            <option value="llm">llm</option>
          </select>
        </label>
        {numericField("最大动作数", "max_actions", 1, 100)}
        {numericField("最大秒数", "max_seconds", 1, 3600)}
        {numericField("最大模型调用数", "max_model_calls", 0, 64)}
        {numericField("无新证据停止轮数", "no_new_evidence_rounds", 1, 10)}
        <label className="flex flex-col gap-1 text-xs text-slate-600">
          数据分区
          <select
            value={draft.data_partition}
            disabled={isUnresolved || create.isPending}
            onChange={(event) => setField("data_partition", event.target.value as LoopDataPartition)}
            className="rounded-md border border-surface-border px-2 py-1.5 text-slate-800"
          >
            <option value="held_out_family">held_out_family</option>
            <option value="training">training</option>
            <option value="validation">validation</option>
            <option value="test">test</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-600 sm:col-span-2">
          授权参考（可选）
          <input
            maxLength={256}
            value={draft.authorization_ref ?? ""}
            disabled={isUnresolved || create.isPending}
            onChange={(event) => setField("authorization_ref", event.target.value)}
            className="rounded-md border border-surface-border px-2 py-1.5 text-slate-800"
          />
        </label>
      </div>
      {draft.max_seconds > 600 && draft.max_actions > 20 && (
        <p className="mt-2 text-xs text-amber-700">最大秒数超过 600 时，最大动作数必须不超过 20。</p>
      )}
      {errorMessage && <p role="alert" className="mt-3 text-xs text-amber-800">{errorMessage}</p>}
      {draft.pending ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button variant="secondary" disabled={reconcile.isPending} onClick={() => void checkStatus()}>
            {reconcile.isPending ? "正在核对…" : "查询并恢复同一提交"}
          </Button>
          {serverStatus?.status === "FAILED" && (
            <Button variant="secondary" onClick={clearPending}>使用新提交号重新编辑</Button>
          )}
          {notFound && (
            <Button variant="secondary" onClick={clearPending}>清除未登记的草稿</Button>
          )}
        </div>
      ) : (
        <Button
          className="mt-3"
          disabled={create.isPending || (draft.max_seconds > 600 && draft.max_actions > 20)}
          onClick={() => void send()}
        >
          {create.isPending ? "正在提交…" : "创建 Loop"}
        </Button>
      )}
      <p className="mt-2 text-[11px] text-slate-500">
        提交编号：<span className="font-mono">{draft.submission_id}</span>。结果不明时只核对同一提交，不会换幂等键盲目重发。
      </p>
    </Card>
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
