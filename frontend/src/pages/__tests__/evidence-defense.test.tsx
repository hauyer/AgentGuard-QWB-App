import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DefensePage } from "../../pages/DefensePage";
import { EvidencePage } from "../../pages/EvidencePage";
import { useAuthStore } from "../../stores/auth-store";

const evidenceResponse = {
  meta: { data_mode: "recorded", fixture_id: "fx-evidence-001", source: "sanitised governed evidence samples", sanitized: true },
  evidence: {
    request_id: "inv-qwb-0001",
    workflow_status: "completed",
    run_status: "completed",
    limitations: ["证据来源于录制回放样例，未经过真实 WARDEN 运行验证。"],
    items: [
      {
        evidence_id: "ev-qwb-0001",
        source_system: "warden",
        warden_run_id: "run-qwb-0001",
        warden_plan_id: "plan-qwb-0001",
        target_type: "tool_call",
        target_ref: "agent-a:settlement:tool-call-023",
        scenario_id: "sc-qwb-001",
        artifact_refs: [],
        evidence_type: "tool_call_observation",
        evidence_level: "observational",
        risk_type: "tool_abuse",
        confidence: 0.72,
        limitations: ["观测性证据：可确认调用发生，不能仅凭此断言因果。"],
        verification_status: "verified",
        run_status: "completed",
        model_version: "agent-suite-2.1",
        causal_validation: null,
        hypothesis: "模型 A 在提示注入诱导下绕过白名单调用内部结算工具。",
      },
      {
        evidence_id: "ev-qwb-0004",
        source_system: "warden",
        warden_run_id: "run-qwb-0001",
        warden_plan_id: "plan-qwb-0001",
        target_type: "tool_call",
        target_ref: "agent-a:settlement:tool-call-027",
        scenario_id: "sc-qwb-001",
        artifact_refs: [],
        evidence_type: "tool_call_intervention",
        evidence_level: "causal_validated",
        risk_type: "tool_abuse",
        confidence: 0.91,
        limitations: ["因果验证结论仅在录制样例的受控条件下成立。"],
        verification_status: "verified",
        run_status: "completed",
        model_version: "agent-suite-2.1",
        causal_validation: { method: "counterfactual_replay", status: "validated", note: "反事实回放通过（演示记录）。" },
        hypothesis: "注入指令是越权工具调用的直接原因。",
      },
    ],
  },
};

const defenseResponse = {
  meta: { data_mode: "recorded", fixture_id: "fx-defense-001", source: "sanitised defense preview samples", sanitized: true },
  defense: {
    schema_version: "0.1",
    run_id: "run-qwb-0001",
    status: "preview_only",
    candidates: [
      {
        candidate_id: "def-qwb-0001",
        risk: "tool_abuse",
        target: "agent-a:settlement",
        operation_type: "block",
        rationale: "证据 ev-qwb-0003/0004 表明结算工具越权调用可被阻断且未降低正常效用。",
        authorization_required: "operator approval",
        estimated_cost: { tokens: 1200, time_seconds: 30 },
        related_evidence: ["ev-qwb-0003", "ev-qwb-0004"],
        status: "pending_approval",
        execution_supported: false,
        execution_reason: "外部防御执行器尚未验证，应用层不执行防御操作。",
      },
    ],
    policy_notes: ["预览仅生成或更新候选，不代表防御已经执行。"],
    execution_performed: false,
    evidence_mode: "recorded",
  },
};

const outcomesResponse = {
  meta: { data_mode: "recorded", fixture_id: "fx-defense-001", sanitized: true },
  outcomes: [
    {
      outcome_id: "hist-def-0001",
      policy: "whitelist-settlement",
      operation_type: "block",
      status: "verified",
      verified_at: "2026-10-19T16:00:00+08:00",
      source: "recorded:exp-qwb-003",
      note: "录制样例：阻断策略在回放测试集上拦截全部越权调用。",
    },
  ],
};

function mockFetchOnce(payload: unknown, status = 200) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } }),
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

describe("EvidencePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useAuthStore.getState().setSession({ role: "analyst", username: "analyst", authEnabled: false });
  });

  it("renders evidence with distinct level badges and never overclaims causality", async () => {
    mockFetchOnce(evidenceResponse);
    renderWithProviders(<EvidencePage />);
    expect(await screen.findByText("ev-qwb-0001")).toBeInTheDocument();
    expect(screen.getByText("OBSERVATIONAL")).toBeInTheDocument();
    expect(screen.getByText("CAUSAL_VALIDATED")).toBeInTheDocument();
    // the causal block is only attached to the validated item
    expect(screen.getByText(/因果验证：counterfactual_replay/)).toBeInTheDocument();
    // observational limitation is preserved
    expect(screen.getByText(/观测性证据：可确认调用发生/)).toBeInTheDocument();
  });

  it("shows replay banner with fixture id", async () => {
    mockFetchOnce(evidenceResponse);
    renderWithProviders(<EvidencePage />);
    expect((await screen.findAllByText(/fx-evidence-001/)).length).toBeGreaterThan(0);
  });
});

describe("DefensePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useAuthStore.getState().setSession({ role: "analyst", username: "analyst", authEnabled: false });
  });

  it("renders candidates as unsupported without an execute button", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(defenseResponse), { status: 200, headers: { "Content-Type": "application/json" } }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(outcomesResponse), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    renderWithProviders(<DefensePage />);
    expect(await screen.findByText("def-qwb-0001")).toBeInTheDocument();
    expect(screen.getByText("UNSUPPORTED")).toBeInTheDocument();
    expect((await screen.findAllByText(/外部防御执行器尚未验证/)).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /执行防御/ })).not.toBeInTheDocument();
    // preview button exists but never claims execution
    expect(screen.getByRole("button", { name: /生成\/更新候选预览/ })).toBeInTheDocument();
    expect(screen.getByText(/execution_performed/)).toBeInTheDocument();
  });

  it("shows demo readonly error when preview is rejected", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(defenseResponse), { status: 200, headers: { "Content-Type": "application/json" } }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(outcomesResponse), { status: 200, headers: { "Content-Type": "application/json" } }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            detail: { error: "DEMO_READONLY", message: "演示模式不执行提交或审批操作：防御预览仅生成或更新候选，录制数据不得假装提交。" },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      );
    renderWithProviders(<DefensePage />);
    await screen.findByText("def-qwb-0001");
    await userEvent.click(screen.getByRole("button", { name: /生成\/更新候选预览/ }));
    await waitFor(() => expect(screen.getByText(/DEMO_READONLY/)).toBeInTheDocument());
  });

  it("renders historical outcomes from demo fixtures", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(defenseResponse), { status: 200, headers: { "Content-Type": "application/json" } }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(outcomesResponse), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    renderWithProviders(<DefensePage />);
    expect(await screen.findByText("hist-def-0001")).toBeInTheDocument();
    expect(screen.getByText(/whitelist-settlement/)).toBeInTheDocument();
  });
});
