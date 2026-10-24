import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ExperiencesPage } from "../../pages/ExperiencesPage";
import { ExperimentsPage } from "../../pages/ExperimentsPage";
import { ReportsPage } from "../../pages/ReportsPage";
import { useAuthStore } from "../../stores/auth-store";

const experimentsResponse = {
  meta: { data_mode: "recorded", fixture_id: "fx-experiments-001", source: "sanitised experiment comparison records", sanitized: true },
  items: [
    {
      experiment_id: "exp-qwb-001",
      run_id: "run-qwb-0001",
      request_id: "inv-qwb-0001",
      scenario_id: "sc-qwb-001",
      model_version: "agent-suite-2.1",
      investigation_strategy: "causal_audit",
      defense_strategy: "whitelist-block",
      execution_status: "completed",
      risk_indicators: { high_risk_paths: 2, tool_abuse_calls: 3, injection_messages: 1 },
      utility: { normal_task_success_rate: 0.98 },
      budget: { tokens: 18400, cost_usd: 0.92, time_seconds: 160 },
      result_source: "recorded:run-qwb-0001",
      created_at: "2026-10-20T09:14:40+08:00",
    },
  ],
};

const reportResponse = {
  meta: { data_mode: "recorded", fixture_id: "fx-reports-001", source: "derived from recorded investigation results", sanitized: true },
  report: {
    run_id: "run-qwb-0001",
    request_id: "inv-qwb-0001",
    experiment_id: "exp-qwb-001",
    scenario_id: "sc-qwb-001",
    status: "completed",
    policy_profile: "read_only",
    created_at: "2026-10-20T09:14:40+08:00",
    findings: [
      {
        finding_id: "fd-qwb-0001",
        risk_type: "tool_abuse",
        summary: "模型 A 在注入诱导下绕过白名单调用内部结算工具。",
        evidence_ids: ["ev-qwb-0001", "ev-qwb-0004"],
        severity: "high",
      },
    ],
    evidence: [
      { evidence_id: "ev-qwb-0001", evidence_level: "observational", verification_status: "verified" },
      { evidence_id: "ev-qwb-0004", evidence_level: "causal_validated", verification_status: "verified" },
    ],
    defense_candidates: [{ candidate_id: "def-qwb-0001", status: "pending_approval", execution_supported: false }],
    limitations: ["报告基于录制演示数据生成；指标与源数据一致，不推断新的因果结论。"],
    source_note: "recorded fixture: fx-inv-001 / fx-evidence-001",
  },
};

const experiencesResponse = {
  meta: { data_mode: "recorded", fixture_id: "fx-experiences-001", source: "sanitised verified experience records", sanitized: true },
  items: [
    {
      experience_id: "xp-qwb-0001",
      scenario_id: "sc-qwb-001",
      risk_type: "tool_abuse",
      title: "结算类工具需默认拒绝并显式白名单",
      action: "对内部结算/支付类工具实施默认拒绝 + 显式白名单。",
      verification_level: "verified",
      recommendation_allowed: true,
      policy_version: "policy-whitelist-v1",
      evidence_refs: ["ev-qwb-0003", "ev-qwb-0004"],
      validation_notes: "录制样例反事实回放验证通过；生产泛化未验证。",
      audit_run_id: "run-qwb-0001",
      applicable_scenarios: ["supply_chain", "finance"],
      created_at: "2026-10-19T16:00:00+08:00",
    },
  ],
  total: 1,
  recommendation_note: "演示经验：允许用于推荐，但不得用于真实因果实验统计。",
};

function mockFetch(payload: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } }),
  );
}

function renderWithProviders(ui: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ExperimentsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useAuthStore.getState().setSession({ role: "viewer", username: "viewer", authEnabled: false });
  });

  it("renders comparison dimensions from the fixture", async () => {
    mockFetch(experimentsResponse);
    renderWithProviders(<ExperimentsPage />);
    expect(await screen.findByText("exp-qwb-001")).toBeInTheDocument();
    expect(screen.getByText("causal_audit")).toBeInTheDocument();
    expect(screen.getByText("whitelist-block")).toBeInTheDocument();
    expect(screen.getByText("98%")).toBeInTheDocument();
    expect(screen.getByText(/18400 \/ 160s/)).toBeInTheDocument();
    expect(screen.getByText(/recorded:run-qwb-0001/)).toBeInTheDocument();
  });

  it("shows explicit live unavailable without trend charts", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: { error: "EXPERIMENTS_UNAVAILABLE", message: "AgentGuard 公共 API 未提供实验对比列表（仅支持单报告读取）；不虚构趋势数据。" },
        }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      ),
    );
    renderWithProviders(<ExperimentsPage />);
    expect(await screen.findByText(/EXPERIMENTS_UNAVAILABLE/)).toBeInTheDocument();
    expect(screen.queryByText(/趋势图/)).not.toBeInTheDocument();
  });
});

describe("ReportsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useAuthStore.getState().setSession({ role: "viewer", username: "viewer", authEnabled: false });
  });

  it("renders report preview with findings, evidence and limitations", async () => {
    mockFetch(reportResponse);
    renderWithProviders(<ReportsPage />);
    expect(await screen.findByText("fd-qwb-0001")).toBeInTheDocument();
    expect(screen.getByText("OBSERVATIONAL")).toBeInTheDocument();
    expect(screen.getByText("CAUSAL_VALIDATED")).toBeInTheDocument();
    expect(screen.getByText("def-qwb-0001")).toBeInTheDocument();
    expect((await screen.findAllByText(/不推断新的因果结论/)).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "下载 JSON" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出 PDF" })).toBeInTheDocument();
  });
});

describe("ExperiencesPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useAuthStore.getState().setSession({ role: "viewer", username: "viewer", authEnabled: false });
  });

  it("renders verified experiences with recommendation flags", async () => {
    mockFetch(experiencesResponse);
    renderWithProviders(<ExperiencesPage />);
    expect(await screen.findByText("xp-qwb-0001")).toBeInTheDocument();
    expect(screen.getByText("已验证")).toBeInTheDocument();
    expect(screen.getByText("允许用于推荐")).toBeInTheDocument();
    expect(screen.getByText(/policy-whitelist-v1/)).toBeInTheDocument();
    expect((await screen.findAllByText(/不得用于真实因果实验统计/)).length).toBeGreaterThan(0);
  });
});
