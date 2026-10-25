import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuthStore } from "../stores/auth-store";
import { useCreateInvestigation, useScenarios } from "../hooks/use-investigations";
import { useProjects } from "../hooks/use-projects";
import { useSystemStatus } from "../hooks/use-system-status";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { ErrorState } from "../components/ui/error-state";
import { PageHeader } from "../components/shared/page-header";
import { PermissionGate } from "../components/shared/permission-gate";
import type {
  AuditMode,
  CaptureTarget,
  CreateInvestigationRequest,
} from "../types/investigations";

const MODES: AuditMode[] = ["observation", "capture_only", "detection", "causal_audit", "defense_evaluation"];

const MODE_LABEL: Record<AuditMode, string> = {
  observation: "观测（observation）",
  capture_only: "仅采集（capture_only）",
  detection: "检测（detection）",
  causal_audit: "因果审计（causal_audit）",
  defense_evaluation: "防御评估（defense_evaluation）",
};

const INPUT =
  "w-full rounded-md border border-surface-border bg-surface px-3 py-1.5 text-sm text-slate-800 outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500";

export function CreateInvestigationPage() {
  const role = useAuthStore((state) => state.role);
  const navigate = useNavigate();
  const create = useCreateInvestigation();
  const scenarios = useScenarios();
  const system = useSystemStatus();

  const [form, setForm] = useState<CreateInvestigationRequest>({
    contract_id: "",
    model_id: "",
    runtime_id: "",
    mode: "causal_audit",
    probe_id: "",
    sae_id: "",
    capture_targets: [{ target_id: "", agent_ids: [], component: "", retain_gradient: false }],
    metadata: {},
    authorization_ref: "",
    scenario_id: "",
    risk_type: "",
    start_run: true,
    wait_for_completion: false,
    timeout_seconds: 30,
    poll_interval_seconds: 1,
  });
  const [metadataText, setMetadataText] = useState("{}");
  const [metadataError, setMetadataError] = useState<string | null>(null);

  // Capability gating: probe/SAE only selectable when AgentGuard advertises them.
  const capabilities = system.data?.capabilities;
  const probeAvailable = Boolean(capabilities?.capabilities["probe_rest"] ?? capabilities?.capabilities["probe"]);
  const saeAvailable = Boolean(capabilities?.capabilities["sae_rest"] ?? capabilities?.capabilities["sae"]);

  // B19: live creations must target a project; demo modes may submit without one.
  const dataMode = system.data?.data_mode;
  const projects = useProjects(50, 0);
  const activeProjects = (projects.data?.items ?? []).filter((project) => project.status === "active");
  const projectRequired = dataMode === "live" || dataMode === undefined;

  const set = <K extends keyof CreateInvestigationRequest>(key: K, value: CreateInvestigationRequest[K]) =>
    setForm((previous) => ({ ...previous, [key]: value }));

  const updateTarget = (index: number, patch: Partial<CaptureTarget>) =>
    setForm((previous) => ({
      ...previous,
      capture_targets: previous.capture_targets.map((target, i) => (i === index ? { ...target, ...patch } : target)),
    }));

  const canSubmit =
    form.contract_id.trim() !== "" &&
    form.model_id.trim() !== "" &&
    form.runtime_id.trim() !== "" &&
    form.capture_targets.length > 0 &&
    form.capture_targets.every((target) => target.target_id.trim() !== "") &&
    metadataError === null &&
    (!projectRequired || form.project_id != null);

  const handleSubmit = () => {
    if (!canSubmit || create.isPending) return;
    create.mutate(
      {
        ...form,
        probe_id: form.probe_id || null,
        sae_id: form.sae_id || null,
        authorization_ref: form.authorization_ref || null,
        scenario_id: form.scenario_id || null,
        risk_type: form.risk_type || null,
        metadata: JSON.parse(metadataText || "{}"),
      },
      {
        onSuccess: (response) => {
          navigate(`/investigations/${encodeURIComponent(response.created.request_id)}`);
        },
      },
    );
  };

  const created = create.data?.created;

  return (
    <div className="space-y-4">
      <PageHeader
        title="新建安全调查"
        description="按 AgentGuard WardenAuditRequest 合同创建调查。提交前会校验威胁契约、模型与运行时标识。"
        actions={
          <Link to="/investigations" className="text-sm text-slate-500 hover:text-slate-700">
            返回列表
          </Link>
        }
      />

      <PermissionGate required="analyst">
        {create.isError && (
          <ErrorState
            title="调查创建失败"
            message={create.error instanceof Error ? create.error.message : "未知错误"}
            code={(create.error as { code?: string }).code}
            requestId={(create.error as { requestId?: string | null }).requestId}
            onRetry={undefined}
          />
        )}

        {created ? (
          <Card title="已提交调查请求">
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Badge variant="ok">已受理</Badge>
                <span className="font-mono text-sm text-slate-700">{created.request_id}</span>
              </div>
              <p className="text-sm text-slate-600">
                状态：<span className="font-medium">{created.status}</span>
                {created.demo_note && <span className="ml-2 text-amber-700">{created.demo_note}</span>}
              </p>
              <p className="text-xs text-slate-500">
                请保留此请求 ID。页面刷新后可通过 /investigations/{created.request_id} 恢复调查。
              </p>
              <Link to={`/investigations/${encodeURIComponent(created.request_id)}`}>
                <Button>查看调查详情</Button>
              </Link>
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card title="威胁契约">
              <div className="space-y-3">
                <label className="block text-xs font-medium text-slate-500">
                  归属项目（project_id）{projectRequired && <span className="text-red-600">*</span>}
                  <select
                    className={INPUT}
                    value={form.project_id ?? ""}
                    onChange={(event) => set("project_id", event.target.value ? Number(event.target.value) : null)}
                  >
                    <option value="">选择项目…</option>
                    {activeProjects.map((project) => (
                      <option key={project.project_id} value={project.project_id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                  <span className="mt-1 block text-[11px] text-slate-400">
                    {dataMode === "live"
                      ? "Live 调查必须归属项目（服务端校验成员权限并审计）"
                      : "演示模式可不选；调查记录进入演示命名空间"}
                  </span>
                </label>
                <label className="block text-xs font-medium text-slate-500">
                  威胁契约 ID（contract_id）
                  <input
                    className={INPUT}
                    value={form.contract_id}
                    placeholder="contract-qwb-001"
                    onChange={(event) => set("contract_id", event.target.value)}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500">
                  模型 ID（model_id）
                  <input
                    className={INPUT}
                    value={form.model_id}
                    placeholder="agent-suite-2.1"
                    onChange={(event) => set("model_id", event.target.value)}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500">
                  WARDEN 运行时 ID（runtime_id）
                  <input
                    className={INPUT}
                    value={form.runtime_id}
                    placeholder="runtime-stub-1"
                    onChange={(event) => set("runtime_id", event.target.value)}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500">
                  审计模式（mode）
                  <select className={INPUT} value={form.mode} onChange={(event) => set("mode", event.target.value as AuditMode)}>
                    {MODES.map((mode) => (
                      <option key={mode} value={mode}>
                        {MODE_LABEL[mode]}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </Card>

            <Card title="采集与运行">
              <div className="space-y-3">
                <label className="block text-xs font-medium text-slate-500">
                  可选 Probe ID（probe_id）
                  <input
                    className={INPUT}
                    value={form.probe_id ?? ""}
                    disabled={!probeAvailable}
                    placeholder={probeAvailable ? "probe-…（可选）" : "AgentGuard 未提供 Probe REST 能力"}
                    onChange={(event) => set("probe_id", event.target.value)}
                  />
                  {!probeAvailable && <span className="text-[11px] text-slate-400">能力不可用：当前 AgentGuard 版本未开放 Probe 接口</span>}
                </label>
                <label className="block text-xs font-medium text-slate-500">
                  可选 SAE ID（sae_id）
                  <input
                    className={INPUT}
                    value={form.sae_id ?? ""}
                    disabled={!saeAvailable}
                    placeholder={saeAvailable ? "sae-…（可选）" : "AgentGuard 未提供 SAE REST 能力"}
                    onChange={(event) => set("sae_id", event.target.value)}
                  />
                  {!saeAvailable && <span className="text-[11px] text-slate-400">能力不可用：当前 AgentGuard 版本未开放 SAE 接口</span>}
                </label>
                <label className="block text-xs font-medium text-slate-500">
                  演示场景（scenario_id）
                  <select
                    className={INPUT}
                    value={form.scenario_id ?? ""}
                    onChange={(event) => set("scenario_id", event.target.value || null)}
                  >
                    <option value="">（不指定）</option>
                    {(scenarios.data?.items ?? []).map((scenario) => (
                      <option key={scenario.scenario_id} value={scenario.scenario_id}>
                        {scenario.scenario_id} · {scenario.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-xs font-medium text-slate-500">
                  风险类型（risk_type）
                  <input
                    className={INPUT}
                    value={form.risk_type ?? ""}
                    placeholder="tool_abuse / prompt_injection / …"
                    onChange={(event) => set("risk_type", event.target.value)}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500">
                  调查授权引用（authorization_ref）
                  <input
                    className={INPUT}
                    value={form.authorization_ref ?? ""}
                    placeholder="auth-ref-…（可选）"
                    onChange={(event) => set("authorization_ref", event.target.value)}
                  />
                </label>
              </div>
            </Card>

            <Card title="采集目标" className="lg:col-span-2">
              <div className="space-y-3">
                {form.capture_targets.map((target, index) => (
                  <div key={index} className="grid grid-cols-1 gap-2 rounded-md border border-surface-border p-3 sm:grid-cols-3">
                    <input
                      className={INPUT}
                      placeholder="target_id（必填）"
                      value={target.target_id}
                      onChange={(event) => updateTarget(index, { target_id: event.target.value })}
                    />
                    <input
                      className={INPUT}
                      placeholder="component，如 settlement"
                      value={target.component ?? ""}
                      onChange={(event) => updateTarget(index, { component: event.target.value })}
                    />
                    <input
                      className={INPUT}
                      placeholder="agent_ids，逗号分隔"
                      value={target.agent_ids.join(",")}
                      onChange={(event) =>
                        updateTarget(index, { agent_ids: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) })
                      }
                    />
                  </div>
                ))}
                <Button
                  variant="secondary"
                  onClick={() =>
                    setForm((previous) => ({
                      ...previous,
                      capture_targets: [...previous.capture_targets, { target_id: "", agent_ids: [], component: "", retain_gradient: false }],
                    }))
                  }
                >
                  添加采集目标
                </Button>
              </div>
            </Card>

            <Card title="运行控制" className="lg:col-span-2">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
                <label className="block text-xs font-medium text-slate-500">
                  超时（秒，1–120）
                  <input
                    type="number"
                    min={1}
                    max={120}
                    className={INPUT}
                    value={form.timeout_seconds}
                    onChange={(event) => set("timeout_seconds", Number(event.target.value))}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500">
                  轮询间隔（秒）
                  <input
                    type="number"
                    min={0.1}
                    max={10}
                    step={0.1}
                    className={INPUT}
                    value={form.poll_interval_seconds}
                    onChange={(event) => set("poll_interval_seconds", Number(event.target.value))}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500">
                  元数据（JSON）
                  <textarea
                    className={INPUT}
                    rows={2}
                    value={metadataText}
                    onChange={(event) => {
                      setMetadataText(event.target.value);
                      try {
                        JSON.parse(event.target.value || "{}");
                        setMetadataError(null);
                      } catch {
                        setMetadataError("JSON 语法错误");
                      }
                    }}
                  />
                  {metadataError && <span className="text-[11px] text-red-600">{metadataError}</span>}
                </label>
                <div className="flex flex-col justify-end gap-2">
                  <label className="flex items-center gap-2 text-xs text-slate-600">
                    <input type="checkbox" checked={form.start_run} onChange={(event) => set("start_run", event.target.checked)} />
                    start_run
                  </label>
                  <label className="flex items-center gap-2 text-xs text-slate-600">
                    <input
                      type="checkbox"
                      checked={form.wait_for_completion}
                      onChange={(event) => set("wait_for_completion", event.target.checked)}
                    />
                    wait_for_completion
                  </label>
                </div>
              </div>
            </Card>

            <div className="flex items-center justify-between lg:col-span-2">
              <p className="text-xs text-slate-500">
                当前角色：<span className="font-mono">{role ?? "未登录"}</span>。不允许提交伪造的 WARDEN 资源 ID。
              </p>
              <Button onClick={handleSubmit} disabled={!canSubmit || create.isPending}>
                {create.isPending ? "提交中…" : "提交调查"}
              </Button>
            </div>
          </div>
        )}
      </PermissionGate>
    </div>
  );
}
