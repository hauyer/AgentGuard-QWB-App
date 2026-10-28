import { useEffect, useMemo, useState, type FormEvent } from "react";
import type { ReactNode } from "react";
import { AlertTriangle, ArrowUpRight, RefreshCw } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { useProjectStudies, useProjectStudy, useProjectStudyAnalyses, useProjectStudyIntegrity, useRegisterProjectStudy, useResearchCapabilities } from "../hooks/use-research";
import { useProjects } from "../hooks/use-projects";
import type { StudyRegistrationPayload } from "../services/research";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { EmptyState } from "../components/ui/empty-state";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";

type Draft = {
  title: string;
  researchQuestion: string;
  primaryHypothesis: string;
  primaryOutcome: string;
  secondaryOutcomes: string;
  analysisMethod: "paired" | "clustered_paired";
  multiplicityMethod: "none" | "holm" | "benjamini_hochberg";
  alpha: string;
  plannedPairs: string;
  plannedCaseFamilies: string;
  seed: string;
  matchingVariables: string;
  inclusionCriteria: string;
  exclusionCriteria: string;
  stoppingRule: string;
  missingDataRule: string;
  deviationsPolicy: string;
  protocolVersion: string;
  codeRevision: string;
  track: "" | "mechanism_testbed" | "live_steganography";
  primaryDirection: "increase" | "decrease" | "two_sided";
};

const INITIAL_DRAFT: Draft = {
  title: "",
  researchQuestion: "",
  primaryHypothesis: "",
  primaryOutcome: "",
  secondaryOutcomes: "",
  analysisMethod: "clustered_paired",
  multiplicityMethod: "holm",
  alpha: "0.05",
  plannedPairs: "",
  plannedCaseFamilies: "",
  seed: "7",
  matchingVariables: "",
  inclusionCriteria: "",
  exclusionCriteria: "",
  stoppingRule: "",
  missingDataRule: "",
  deviationsPolicy: "Any deviation is logged with timestamp, rationale, and whether it was decided before outcome inspection.",
  protocolVersion: "1",
  codeRevision: "unspecified",
  track: "",
  primaryDirection: "two_sided",
};

function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

function modeVariant(mode?: string): "ok" | "warn" | "danger" | "neutral" {
  if (mode === "live") return "ok";
  if (mode === "synthetic") return "warn";
  if (mode === "unavailable") return "danger";
  return "neutral";
}

function statusVariant(status: string): "ok" | "warn" | "danger" | "info" | "neutral" {
  if (status === "SUPPORTED_AND_READY" || status === "LINKED") return "ok";
  if (status === "SUPPORTED_BUT_BLOCKED" || status === "SUBMISSION_AMBIGUOUS" || status === "SUBMITTING") return "warn";
  if (status === "UNAVAILABLE" || status === "REJECTED") return "danger";
  if (status === "UNSUPPORTED") return "neutral";
  return "info";
}

function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function ResearchWorkbenchPage() {
  const projects = useProjects(200);
  const capabilities = useResearchCapabilities();
  const [searchParams, setSearchParams] = useSearchParams();
  const availableProjects = projects.data?.items ?? [];
  const requestedProjectId = Number(searchParams.get("projectId"));
  const projectId = availableProjects.some((project) => project.project_id === requestedProjectId)
    ? requestedProjectId
    : availableProjects[0]?.project_id ?? 0;
  const studies = useProjectStudies(projectId);
  const registerStudy = useRegisterProjectStudy(projectId);
  const [selectedStudyId, setSelectedStudyId] = useState<string | null>(null);
  const detail = useProjectStudy(projectId, selectedStudyId);
  const integrity = useProjectStudyIntegrity(projectId, selectedStudyId);
  const analyses = useProjectStudyAnalyses(projectId, selectedStudyId);
  const [draft, setDraft] = useState<Draft>(INITIAL_DRAFT);
  const [armsJson, setArmsJson] = useState("[]");
  const [submissionKey, setSubmissionKey] = useState(newIdempotencyKey);
  const [previewPayload, setPreviewPayload] = useState<StudyRegistrationPayload | null>(null);
  const [lastPayload, setLastPayload] = useState<StudyRegistrationPayload | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (projectId > 0 && searchParams.get("projectId") !== String(projectId)) {
      const next = new URLSearchParams(searchParams);
      next.set("projectId", String(projectId));
      setSearchParams(next, { replace: true });
    }
  }, [projectId, searchParams, setSearchParams]);

  useEffect(() => {
    if (registerStudy.data?.submission.status === "LINKED") {
      setSelectedStudyId(registerStudy.data.submission.study_id);
      setDraft(INITIAL_DRAFT);
      setArmsJson("[]");
      setPreviewPayload(null);
      setLastPayload(null);
      setSubmissionKey(newIdempotencyKey());
    }
  }, [registerStudy.data]);

  const capabilityItems = capabilities.data?.report.capabilities ?? [];
  const sourceLabels = useMemo(() => ({
    live: "LIVE",
    recorded: "RECORDED",
    synthetic: "SYNTHETIC",
    unavailable: "UNAVAILABLE",
  }), []);
  const currentMode = capabilities.data?.meta.data_mode;
  const ambiguousResult = registerStudy.data?.submission.status === "SUBMISSION_AMBIGUOUS";
  const uncertainError = registerStudy.isError &&
    ((registerStudy.error as { status?: number })?.status === 502 ||
     (registerStudy.error as { status?: number })?.status === 503);

  const updateDraft = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setDraft((previous) => ({ ...previous, [key]: value }));
    setSubmissionKey(newIdempotencyKey());
    setPreviewPayload(null);
    setLastPayload(null);
    setFormError(null);
    registerStudy.reset();
  };

  const buildPayload = (): StudyRegistrationPayload => {
    let arms: unknown;
    try {
      arms = JSON.parse(armsJson);
    } catch {
      throw new Error("实验臂 JSON 格式无效。");
    }
    if (!Array.isArray(arms) || arms.length < 2) throw new Error("请至少填写两个实验臂，以冻结基线和对照条件。");
    const armIds = new Set<string>();
    const armRoles = new Set(["baseline", "treatment", "sham", "irrelevant", "randomization"]);
    for (const arm of arms) {
      if (!arm || typeof arm !== "object" || Array.isArray(arm)) throw new Error("每个实验臂都必须是 JSON 对象。");
      const candidate = arm as Record<string, unknown>;
      if (!["arm_id", "role", "method_id", "method_version"].every((key) => typeof candidate[key] === "string" && candidate[key])) {
        throw new Error("每个实验臂都需要 arm_id、role、method_id 和 method_version。");
      }
      if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(candidate.arm_id as string)) {
        throw new Error("实验臂 arm_id 格式无效。");
      }
      if (!armRoles.has(candidate.role as string)) throw new Error("实验臂 role 不符合 RC5 合同。");
      if (armIds.has(candidate.arm_id as string)) throw new Error("实验臂 arm_id 必须唯一。");
      armIds.add(candidate.arm_id as string);
      if (candidate.parameter_sha256 !== undefined && candidate.parameter_sha256 !== null &&
          (typeof candidate.parameter_sha256 !== "string" || !/^[0-9a-f]{64}$/.test(candidate.parameter_sha256))) {
        throw new Error("实验臂 parameter_sha256 必须是 64 位小写 SHA-256。");
      }
    }
    const alpha = Number(draft.alpha);
    const seed = Number(draft.seed);
    if (!Number.isFinite(alpha) || alpha <= 0 || alpha >= 0.5) throw new Error("显著性阈值 alpha 必须大于 0 且小于 0.5。");
    if (!Number.isInteger(seed)) throw new Error("随机种子必须是整数。");
    const matchingVariables = draft.matchingVariables.split(",").map((item) => item.trim()).filter(Boolean);
    const inclusionCriteria = draft.inclusionCriteria.split("\n").map((item) => item.trim()).filter(Boolean);
    const exclusionCriteria = draft.exclusionCriteria.split("\n").map((item) => item.trim()).filter(Boolean);
    const payload: StudyRegistrationPayload = {
      schema_version: "0.1",
      title: draft.title.trim(),
      research_question: draft.researchQuestion.trim(),
      primary_hypothesis: draft.primaryHypothesis.trim(),
      primary_outcome: draft.primaryOutcome.trim(),
      primary_direction: draft.primaryDirection,
      secondary_outcomes: draft.secondaryOutcomes.split(",").map((item) => item.trim()).filter(Boolean),
      analysis_method: draft.analysisMethod,
      multiplicity_method: draft.multiplicityMethod,
      alpha,
      planned_pairs: Number(draft.plannedPairs),
      planned_case_families: Number(draft.plannedCaseFamilies),
      seed,
      matching_variables: matchingVariables,
      inclusion_criteria: inclusionCriteria,
      exclusion_criteria: exclusionCriteria,
      stopping_rule: draft.stoppingRule.trim(),
      missing_data_rule: draft.missingDataRule.trim(),
      deviations_policy: draft.deviationsPolicy.trim(),
      protocol_version: draft.protocolVersion.trim(),
      code_revision: draft.codeRevision.trim(),
      arms: arms as Array<Record<string, unknown>>,
    };
    if (draft.track) payload.track = draft.track;
    return payload;
  };

  const submitPayload = (payload: StudyRegistrationPayload) => {
    setLastPayload(payload);
    registerStudy.mutate({ payload, idempotencyKey: submissionKey });
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    try {
      setPreviewPayload(buildPayload());
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "请检查预注册内容。");
    }
  };

  return (
    <div className="mx-auto max-w-[1500px] space-y-5">
      <PageHeader
        title="研究工作台"
        description="查看 AgentGuard RC5 研究能力，在项目内预注册 Study，并追踪上游记录与证据限制。"
        actions={(
          <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
            当前项目
            <select
              aria-label="当前项目"
              className="h-9 max-w-[15rem] rounded-md border border-surface-border bg-white px-2 text-sm text-slate-800"
              value={projectId || ""}
              onChange={(event) => {
                setSelectedStudyId(null);
                registerStudy.reset();
                setPreviewPayload(null);
                setLastPayload(null);
                const next = new URLSearchParams(searchParams);
                next.set("projectId", event.target.value);
                setSearchParams(next);
              }}
              disabled={availableProjects.length === 0}
            >
              {availableProjects.length === 0 && <option value="">没有可用项目</option>}
              {availableProjects.map((project) => (
                <option key={project.project_id} value={project.project_id}>{project.name}</option>
              ))}
            </select>
          </label>
        )}
      />

      {projects.isLoading && <p className="text-sm text-slate-500">正在读取项目权限…</p>}
      {projects.error && (
        <ErrorState
          title="项目列表不可用"
          message={projects.error instanceof Error ? projects.error.message : "无法读取当前用户可访问的项目。"}
          onRetry={() => void projects.refetch()}
          retrying={projects.isFetching}
        />
      )}

      <Card
        title="研究能力诊断"
        description={capabilities.data?.meta.source_note ?? "能力状态来自 AgentGuard RC5；API 连通不代表 WARDEN 可执行。"}
        action={capabilities.data && (
          <Badge variant={modeVariant(currentMode)}>{sourceLabels[currentMode as keyof typeof sourceLabels] ?? "UNKNOWN"}</Badge>
        )}
      >
        {capabilities.isLoading && <p className="text-sm text-slate-500">正在读取能力状态…</p>}
        {capabilities.error && (
          <ErrorState
            title="能力诊断不可用"
            message={capabilities.error instanceof Error ? capabilities.error.message : "AgentGuard 未返回研究能力报告。"}
            onRetry={() => void capabilities.refetch()}
            retrying={capabilities.isFetching}
          />
        )}
        {capabilities.data && (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
              <span>后端状态 <strong className="text-slate-700">{capabilities.data.report.backend_status}</strong></span>
              <span>来源版本 <code className="font-mono">{capabilities.data.report.source_version ?? "未知"}</code></span>
              <span>API <code className="font-mono">{capabilities.data.report.source_api_version ?? "未知"}</code></span>
              <span>观察时间 {capabilities.data.report.observed_at}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-surface-border text-slate-500">
                    <th className="py-2 pr-3 font-medium">能力</th>
                    <th className="py-2 pr-3 font-medium">状态</th>
                    <th className="py-2 pr-3 font-medium">WARDEN 声明</th>
                    <th className="py-2 font-medium">阻塞原因</th>
                  </tr>
                </thead>
                <tbody>
                  {capabilityItems.map((item) => (
                    <tr key={item.capability} className="border-b border-surface-border/60 align-top text-slate-700">
                      <td className="py-2 pr-3 font-mono">{item.capability}</td>
                      <td className="py-2 pr-3"><Badge variant={statusVariant(item.status)}>{item.status}</Badge></td>
                      <td className="py-2 pr-3">{item.advertised_by_warden === null ? "未知" : item.advertised_by_warden ? "是" : "否"}</td>
                      <td className="py-2 text-slate-500">{item.blockers.length ? item.blockers.join(" · ") : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {capabilities.data.report.limitations.length > 0 && (
              <ul className="mt-3 list-inside list-disc space-y-1 text-xs text-slate-500">
                {capabilities.data.report.limitations.map((item) => <li key={item}>{item}</li>)}
              </ul>
            )}
          </>
        )}
      </Card>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(340px,0.7fr)]">
        <Card
          title="项目 Study 登记"
          description="预注册只保存协议和实验臂定义，不会启动 WARDEN 或生成实验结果。每次提交使用持久幂等意图。"
        >
          {projectId <= 0 ? (
            <EmptyState title="先选择一个有权限的项目" description="Study 记录必须绑定到项目。" />
          ) : (
            <form className="grid gap-3 sm:grid-cols-2" onSubmit={submit}>
              <Field label="Study 标题" required className="sm:col-span-2">
                <input required minLength={8} maxLength={240} value={draft.title} onChange={(event) => updateDraft("title", event.target.value)} className={inputClass} />
              </Field>
              <Field label="研究问题" required className="sm:col-span-2">
                <textarea required minLength={12} maxLength={2000} rows={2} value={draft.researchQuestion} onChange={(event) => updateDraft("researchQuestion", event.target.value)} className={inputClass} />
              </Field>
              <Field label="主要假设" required className="sm:col-span-2">
                <textarea required minLength={12} maxLength={2000} rows={2} value={draft.primaryHypothesis} onChange={(event) => updateDraft("primaryHypothesis", event.target.value)} className={inputClass} />
              </Field>
              <Field label="主要结果变量" required>
                <input required pattern="[a-zA-Z][a-zA-Z0-9_.-]{0,79}" value={draft.primaryOutcome} onChange={(event) => updateDraft("primaryOutcome", event.target.value)} className={inputClass} />
              </Field>
              <Field label="预期方向">
                <select value={draft.primaryDirection} onChange={(event) => updateDraft("primaryDirection", event.target.value as Draft["primaryDirection"])} className={inputClass}>
                  <option value="two_sided">双侧</option>
                  <option value="increase">增加</option>
                  <option value="decrease">减少</option>
                </select>
              </Field>
              <Field label="次要结果变量（逗号分隔）">
                <input value={draft.secondaryOutcomes} onChange={(event) => updateDraft("secondaryOutcomes", event.target.value)} className={inputClass} />
              </Field>
              <Field label="分析方法" required>
                <select value={draft.analysisMethod} onChange={(event) => updateDraft("analysisMethod", event.target.value as Draft["analysisMethod"])} className={inputClass}>
                  <option value="clustered_paired">clustered_paired</option>
                  <option value="paired">paired</option>
                </select>
              </Field>
              <Field label="多重比较校正" required>
                <select value={draft.multiplicityMethod} onChange={(event) => updateDraft("multiplicityMethod", event.target.value as Draft["multiplicityMethod"])} className={inputClass}>
                  <option value="holm">holm</option>
                  <option value="benjamini_hochberg">benjamini_hochberg</option>
                  <option value="none">none</option>
                </select>
              </Field>
              <Field label="显著性阈值 alpha" required>
                <input required type="number" min="0.001" max="0.499" step="0.001" value={draft.alpha} onChange={(event) => updateDraft("alpha", event.target.value)} className={inputClass} />
              </Field>
              <Field label="计划配对数" required>
                <input required type="number" min={2} max={100000} value={draft.plannedPairs} onChange={(event) => updateDraft("plannedPairs", event.target.value)} className={inputClass} />
              </Field>
              <Field label="计划案例族数量" required>
                <input required type="number" min={2} max={10000} value={draft.plannedCaseFamilies} onChange={(event) => updateDraft("plannedCaseFamilies", event.target.value)} className={inputClass} />
              </Field>
              <Field label="随机种子" required>
                <input required type="number" step={1} value={draft.seed} onChange={(event) => updateDraft("seed", event.target.value)} className={inputClass} />
              </Field>
              <Field label="协议版本" required>
                <input required maxLength={80} value={draft.protocolVersion} onChange={(event) => updateDraft("protocolVersion", event.target.value)} className={inputClass} />
              </Field>
              <Field label="代码修订" required>
                <input required maxLength={128} value={draft.codeRevision} onChange={(event) => updateDraft("codeRevision", event.target.value)} className={inputClass} />
              </Field>
              <Field label="匹配变量（逗号分隔）" required>
                <input required value={draft.matchingVariables} onChange={(event) => updateDraft("matchingVariables", event.target.value)} className={inputClass} />
              </Field>
              <Field label="研究 Track">
                <select value={draft.track} onChange={(event) => updateDraft("track", event.target.value as Draft["track"])} className={inputClass}>
                  <option value="">不指定</option>
                  <option value="mechanism_testbed">mechanism_testbed</option>
                  <option value="live_steganography">live_steganography</option>
                </select>
              </Field>
              <Field label="纳入条件（每行一条）" required className="sm:col-span-2">
                <textarea required rows={2} value={draft.inclusionCriteria} onChange={(event) => updateDraft("inclusionCriteria", event.target.value)} className={inputClass} />
              </Field>
              <Field label="排除条件（每行一条）" className="sm:col-span-2">
                <textarea rows={2} value={draft.exclusionCriteria} onChange={(event) => updateDraft("exclusionCriteria", event.target.value)} className={inputClass} />
              </Field>
              <Field label="停止规则" required>
                <textarea required minLength={8} maxLength={1000} rows={3} value={draft.stoppingRule} onChange={(event) => updateDraft("stoppingRule", event.target.value)} className={inputClass} />
              </Field>
              <Field label="缺失数据规则" required>
                <textarea required minLength={8} maxLength={1000} rows={3} value={draft.missingDataRule} onChange={(event) => updateDraft("missingDataRule", event.target.value)} className={inputClass} />
              </Field>
              <Field label="协议偏离记录规则" required className="sm:col-span-2">
                <textarea required minLength={8} maxLength={1000} rows={2} value={draft.deviationsPolicy} onChange={(event) => updateDraft("deviationsPolicy", event.target.value)} className={inputClass} />
              </Field>
              <Field label="实验臂定义 JSON" className="sm:col-span-2">
                <textarea rows={5} spellCheck={false} value={armsJson} onChange={(event) => { setArmsJson(event.target.value); setSubmissionKey(newIdempotencyKey()); setPreviewPayload(null); setLastPayload(null); }} className={`${inputClass} font-mono text-xs`} aria-describedby="arms-help" />
                <span id="arms-help" className="text-[11px] leading-4 text-slate-500">每个实验臂需提供 arm_id、role、method_id、method_version。这里只登记计划，不会执行。</span>
              </Field>
              {previewPayload && (
                <section aria-label="不可变注册摘要" className="sm:col-span-2 rounded-md border border-brand-200 bg-brand-50/40 p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-800">预览不可变注册摘要</h3>
                      <p className="mt-1 text-xs text-slate-600">确认后会把下方这份完整正文提交到当前项目。修改表单会清除此摘要并生成新的幂等键。</p>
                    </div>
                    <Badge variant="neutral">待确认 · 尚未提交</Badge>
                  </div>
                  <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
                    <div><dt className="text-slate-500">Study</dt><dd className="mt-0.5 break-words font-medium text-slate-800">{previewPayload.title}</dd></div>
                    <div><dt className="text-slate-500">主要结果变量</dt><dd className="mt-0.5 font-mono text-slate-800">{previewPayload.primary_outcome}</dd></div>
                    <div><dt className="text-slate-500">计划样本</dt><dd className="mt-0.5 text-slate-800">{previewPayload.planned_pairs} 对 · {previewPayload.planned_case_families} 个案例族</dd></div>
                  </dl>
                  <details className="mt-3">
                    <summary className="cursor-pointer text-xs font-medium text-brand-800">查看完整预注册正文</summary>
                    <pre className="mt-2 max-h-72 overflow-auto rounded-md border border-surface-border bg-white p-3 font-mono text-[10px] leading-5 text-slate-700">{pretty(previewPayload)}</pre>
                  </details>
                  <div className="mt-3 flex flex-wrap justify-end gap-2 border-t border-brand-200 pt-3">
                    <Button type="button" variant="secondary" onClick={() => setPreviewPayload(null)}>返回修改</Button>
                    <Button type="button" disabled={registerStudy.isPending} onClick={() => submitPayload(previewPayload)}>
                      {registerStudy.isPending ? "正在登记…" : "确认并登记 Study"}
                    </Button>
                  </div>
                </section>
              )}
              {formError && <p role="alert" className="sm:col-span-2 rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">{formError}</p>}
              {registerStudy.error && !uncertainError && (
                <p role="alert" className="sm:col-span-2 rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">
                  {registerStudy.error instanceof Error ? registerStudy.error.message : "Study 注册失败。"}
                </p>
              )}
              {(ambiguousResult || uncertainError) && lastPayload && (
                <div role="status" className="sm:col-span-2 flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                  <span>提交结果不确定。使用原正文和同一幂等键重试可对账；系统不会自动重发。</span>
                  <Button type="button" variant="secondary" disabled={registerStudy.isPending} onClick={() => submitPayload(lastPayload)}>
                    <RefreshCw className="mr-1.5 h-3.5 w-3.5" />使用同一密钥重试
                  </Button>
                </div>
              )}
              {registerStudy.data?.submission.status === "LINKED" && (
                <p role="status" className="sm:col-span-2 rounded-md border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-800">
                  Study 已登记并绑定到当前项目。Study ID：<code className="font-mono">{registerStudy.data.submission.study_id}</code>
                </p>
              )}
              <div className="sm:col-span-2 flex items-center justify-between border-t border-surface-border pt-3">
                <span className="text-[11px] text-slate-500">上游来源 {currentMode ? sourceLabels[currentMode as keyof typeof sourceLabels] ?? currentMode : "UNKNOWN"} · 密钥由浏览器生成并只以哈希形式保存在 App</span>
                <Button type="submit" disabled={registerStudy.isPending || projectId <= 0}>
                  预览注册摘要
                </Button>
              </div>
            </form>
          )}
        </Card>

        <div className="space-y-5">
          <Card title="项目 Study 列表" description={studies.data?.meta.source_note ?? "列表只读取 App 本地项目映射。"} action={<Badge variant="neutral">RECORDED</Badge>}>
            {studies.isLoading && <p className="text-sm text-slate-500">正在读取项目登记…</p>}
            {studies.error && (
              <ErrorState title="Study 列表不可用" message={studies.error instanceof Error ? studies.error.message : "无法读取项目 Study。"} onRetry={() => void studies.refetch()} retrying={studies.isFetching} />
            )}
            {studies.data && studies.data.items.length === 0 && (
              <EmptyState title="此项目还没有 Study" description="填写左侧预注册表单后，App 会先持久化意图，再提交到 AgentGuard。" />
            )}
            {studies.data && studies.data.items.length > 0 && (
              <div className="space-y-2">
                <p className="text-[11px] text-slate-500">共 {studies.data.total} 条项目登记</p>
                {studies.data.items.map((item) => (
                  <div key={`${item.study_id ?? "pending"}:${item.request_id}`} className="rounded-md border border-surface-border p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="break-words text-sm font-medium text-slate-800">{item.title}</p>
                        <p className="mt-1 truncate font-mono text-[10px] text-slate-500">{item.study_id ?? item.request_id}</p>
                      </div>
                      <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-slate-500">
                      <span>{item.track ?? "未指定 Track"} · {item.source.origin_mode.toUpperCase()}</span>
                      {item.study_id && (
                        <button type="button" onClick={() => setSelectedStudyId(item.study_id)} className="inline-flex items-center gap-1 text-brand-700 hover:underline">
                          查看详情 <ArrowUpRight className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                    {item.error_message && <p className="mt-2 text-[11px] text-amber-800">{item.error_message}</p>}
                  </div>
                ))}
              </div>
            )}
          </Card>

          {selectedStudyId && (
            <Card title="Study 详情与验证" description={selectedStudyId}>
              {detail.isLoading && <p className="text-sm text-slate-500">正在读取上游详情…</p>}
              {detail.error && <ErrorState title="Study 详情不可用" message={detail.error instanceof Error ? detail.error.message : "无法读取已映射 Study。"} onRetry={() => void detail.refetch()} retrying={detail.isFetching} />}
              {detail.data && (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <Badge variant={modeVariant(detail.data.meta.data_mode)}>{detail.data.meta.data_mode.toUpperCase()}</Badge>
                    <span className="text-slate-500">AgentGuard <code className="font-mono">{detail.data.meta.agentguard_commit.slice(0, 7)}</code></span>
                    <span className="text-slate-500">注册 SHA-256 <code className="break-all font-mono">{detail.data.project_registration.registration_sha256}</code></span>
                  </div>
                  <pre className="max-h-72 overflow-auto rounded-md bg-slate-50 p-3 text-[10px] leading-5 text-slate-700">{pretty(detail.data.study)}</pre>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-md border border-surface-border p-3">
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="text-xs font-semibold text-slate-700">注册完整性</h3>
                        {integrity.data && <Badge variant={integrity.data.integrity.integrity_status === "valid" ? "ok" : "warn"}>{String(integrity.data.integrity.integrity_status ?? "UNKNOWN")}</Badge>}
                      </div>
                      {integrity.isLoading && <p className="mt-2 text-xs text-slate-500">读取中…</p>}
                      {integrity.data && <pre className="mt-2 max-h-32 overflow-auto text-[10px] text-slate-600">{pretty(integrity.data.integrity)}</pre>}
                      {integrity.error && <p className="mt-2 text-xs text-red-700">完整性信息不可用。</p>}
                    </div>
                    <div className="rounded-md border border-surface-border p-3">
                      <h3 className="text-xs font-semibold text-slate-700">分析记录</h3>
                      {analyses.isLoading && <p className="mt-2 text-xs text-slate-500">读取中…</p>}
                      {analyses.data && analyses.data.items.length === 0 && <p className="mt-2 text-xs text-slate-500">上游没有返回分析记录；App 不生成替代结果。</p>}
                      {analyses.data && analyses.data.items.length > 0 && <pre className="mt-2 max-h-32 overflow-auto text-[10px] text-slate-600">{pretty(analyses.data.items)}</pre>}
                      {analyses.error && <p className="mt-2 text-xs text-red-700">分析记录不可用。</p>}
                    </div>
                  </div>
                </div>
              )}
            </Card>
          )}

          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="font-semibold">执行与分析门控仍关闭</p>
                <p className="mt-1 leading-5">WARDEN Live Gate 尚未验证；没有已核验的真实执行器和工件内容来源。App 不开放 Run 执行或分析写入，RC5 的 measured 输入在工件验证前仍会被拒绝。</p>
                <p className="mt-2 font-mono text-[10px]">合同来源 d85aa97 · HTTP Smoke NOT_RUN</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const inputClass = "mt-1 block w-full rounded-md border border-surface-border bg-white px-2.5 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100";

function Field({
  label,
  required,
  className,
  children,
}: {
  label: string;
  required?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <label className={className ?? "block text-xs font-medium text-slate-700"}>
      {label}{required && <span className="ml-1 text-red-600" aria-label="必填">*</span>}
      {children}
    </label>
  );
}
