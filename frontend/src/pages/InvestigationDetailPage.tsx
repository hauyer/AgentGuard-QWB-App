import { Link, useNavigate, useParams } from "react-router-dom";
import { useEffect, useState } from "react";

import { useInvestigation, useTimeline } from "../hooks/use-investigations";
import {
  useCreateInvestigationLoop,
  useInvestigationLoopSubmission,
  useInvestigationLoops,
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

      <InvestigationLoopList
        requestId={requestId}
        dataMode={meta.data_mode}
        hasProject={((meta as MetaInfo & { project_ids?: number[] }).project_ids ?? []).length > 0}
      />

      <LoopCreatePanel
        requestId={requestId}
        dataMode={meta.data_mode}
        hasProject={((meta as MetaInfo & { project_ids?: number[] }).project_ids ?? []).length > 0}
      />
    </div>
  );
}

function InvestigationLoopList({
  requestId,
  dataMode,
  hasProject,
}: {
  requestId: string;
  dataMode: string;
  hasProject: boolean;
}) {
  const liveProject = dataMode === "live" && hasProject;
  const loops = useInvestigationLoops(requestId, liveProject);
  const ownershipVerified = loops.data?.meta.ownership_verified === true;

  if (!liveProject) {
    return (
      <Card title="多轮调查" description="仅展示已授权调查对应的 Loop">
        <p className="text-sm text-slate-500">
          {hasProject ? `当前 ${dataMode.toUpperCase()} 数据源没有可验证的 Live Loop 列表。` : "该调查没有已验证的项目归属。"}
        </p>
      </Card>
    );
  }

  if (loops.isPending) {
    return <Card title="多轮调查"><p className="text-sm text-slate-500">正在读取 Loop 列表…</p></Card>;
  }

  if (loops.isError || !loops.data) {
    return (
      <Card title="多轮调查" description="AgentGuard 实时数据">
        <ErrorState
          title="Loop 列表不可用"
          message={loops.error instanceof Error ? loops.error.message : "无法读取 Loop 列表"}
          onRetry={() => void loops.refetch()}
          retrying={loops.isFetching}
        />
      </Card>
    );
  }

  const items = loops.data.items ?? [];
  return (
    <Card title="多轮调查" description="AgentGuard · LIVE" action={(
      <Button variant="secondary" onClick={() => void loops.refetch()} disabled={loops.isFetching}>
        {loops.isFetching ? "刷新中…" : "刷新"}
      </Button>
    )}>
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">此基础调查尚无 Loop。</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-xs">
            <thead>
              <tr className="border-b border-surface-border text-left text-[11px] text-slate-500">
                <th className="py-2 pr-4 font-medium">Loop</th>
                <th className="py-2 pr-4 font-medium">阶段</th>
                <th className="py-2 pr-4 font-medium">策略</th>
                <th className="py-2 pr-4 text-right font-medium">已执行轮数</th>
                <th className="py-2 pr-4 font-medium">停止原因</th>
                <th className="py-2 pr-4 font-medium">创建时间</th>
                <th className="py-2 font-medium">来源</th>
              </tr>
            </thead>
            <tbody>
              {items.map((loop) => (
                <tr key={loop.loop_id} className="border-b border-slate-100 last:border-0">
                  <td className="py-2.5 pr-4 font-mono">
                    {ownershipVerified ? (
                      <Link
                        className="font-medium text-brand-700 hover:text-brand-900 hover:underline"
                        to={`/investigation-journal?loop_id=${encodeURIComponent(loop.loop_id)}`}
                      >
                        {loop.loop_id}
                      </Link>
                    ) : loop.loop_id}
                  </td>
                  <td className="py-2.5 pr-4">{loop.phase ?? "未提供"}</td>
                  <td className="py-2.5 pr-4">{loop.strategy ?? "未提供"}</td>
                  <td className="py-2.5 pr-4 text-right">
                    {typeof loop.rounds_executed === "number" ? loop.rounds_executed : loop.metrics?.rounds_executed ?? "未提供"}
                  </td>
                  <td className="max-w-48 truncate py-2.5 pr-4" title={loop.stop_reason ?? undefined}>{loop.stop_reason ?? "未提供"}</td>
                  <td className="py-2.5 pr-4">{loop.created_at ?? "未提供"}</td>
                  <td className="py-2.5"><span className="rounded bg-emerald-50 px-1.5 py-1 text-[10px] text-emerald-700">LIVE</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
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
  const [reconciliationNote, setReconciliationNote] = useState("");
  const [reconciliationLoopId, setReconciliationLoopId] = useState("");
  const create = useCreateInvestigationLoop(requestId);
  const reconcile = useReconcileInvestigationLoop(requestId);
  const submission = useInvestigationLoopSubmission(requestId, draft.submission_id, draft.pending);
  const loops = useInvestigationLoops(requestId, dataMode === "live" && hasProject && draft.pending);

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
  const checkStatus = async (
    action: "resume" | "associate_loop" | "confirm_not_created" = "resume",
  ) => {
    setErrorMessage(null);
    try {
      const body = action === "resume"
        ? { action }
        : {
          action,
          ...(action === "associate_loop" ? { loop_id: reconciliationLoopId } : {}),
          operator_note: reconciliationNote.trim(),
        };
      const response = await reconcile.mutateAsync({ submissionId: draft.submission_id, body });
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
          {serverStatus?.status === "PREPARED" && (
            <Button variant="secondary" disabled={reconcile.isPending} onClick={() => void checkStatus("resume")}>
              {reconcile.isPending ? "正在恢复…" : "恢复尚未发送的提交"}
            </Button>
          )}
          {serverStatus?.status === "SUBMISSION_AMBIGUOUS" && (
            <div className="w-full space-y-2 rounded-md border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs text-amber-900">
                上游未提供本次提交的关联标识。请先在 AgentGuard 核实，再选择新出现的 Loop 或确认没有创建。
              </p>
              <select
                aria-label="选择待关联的 Loop"
                value={reconciliationLoopId}
                onChange={(event) => setReconciliationLoopId(event.target.value)}
                className="w-full rounded-md border border-surface-border bg-white px-2 py-1.5 text-xs text-slate-800"
              >
                <option value="">选择已核实为本次提交的 Loop</option>
                {(loops.data?.items ?? []).map((loop) => (
                  <option key={loop.loop_id} value={loop.loop_id}>{loop.loop_id} · {loop.phase ?? "状态未提供"}</option>
                ))}
              </select>
              <label className="block text-xs text-slate-700">
                核对记录（至少 10 个字符）
                <input
                  value={reconciliationNote}
                  onChange={(event) => setReconciliationNote(event.target.value)}
                  maxLength={500}
                  className="mt-1 w-full rounded-md border border-surface-border bg-white px-2 py-1.5"
                  placeholder="例如：已核对 AgentGuard 审计记录 AG-123"
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  disabled={reconcile.isPending || !reconciliationLoopId || reconciliationNote.trim().length < 10}
                  onClick={() => void checkStatus("associate_loop")}
                >
                  关联所选 Loop
                </Button>
                <Button
                  variant="secondary"
                  disabled={reconcile.isPending || reconciliationNote.trim().length < 10}
                  onClick={() => {
                    if (window.confirm("确认已在 AgentGuard 核查并确认没有创建本次 Loop？这会释放该调查的创建锁。")) {
                      void checkStatus("confirm_not_created");
                    }
                  }}
                >
                  确认未创建
                </Button>
              </div>
            </div>
          )}
          {serverStatus?.status === "SUBMITTING" && (
            <p className="text-xs text-amber-800">AgentGuard 请求仍在处理中；请稍后查询，不要发起新的提交。</p>
          )}
          {serverStatus?.status === "LINK_PENDING" && (
            <Button variant="secondary" disabled={reconcile.isPending} onClick={() => void checkStatus("resume")}>
              {reconcile.isPending ? "正在补全项目关联…" : "补全本地项目关联"}
            </Button>
          )}
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
