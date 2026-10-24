import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DemoCenterPage } from "../../pages/DemoCenterPage";
import { useAuthStore } from "../../stores/auth-store";

const overviewResponse = {
  meta: {
    data_mode: "synthetic",
    fixture_id: "fx-scenarios-001",
    source: "generated for QWB demo",
    sanitized: true,
    not_provable: ["场景不构成真实威胁环境复现。"],
  },
  flow: [
    { step: 1, title: "打开平台", path: "/", fixture_ref: null, description: "系统总览。" },
    { step: 2, title: "选择演示场景", path: "/demo", fixture_ref: "fx-scenarios-001", description: "场景。" },
    { step: 3, title: "查看 Agent 交互", path: "/interaction-graph", fixture_ref: "fx-graph-001", description: "图谱。" },
    { step: 4, title: "查看调查过程", path: "/investigations/inv-qwb-0001", fixture_ref: "fx-inv-001", description: "时间线。" },
    { step: 5, title: "查看风险发现", path: "/investigations/inv-qwb-0001", fixture_ref: "fx-inv-001", description: "结果。" },
    { step: 6, title: "查看证据和限制", path: "/evidence?request_id=inv-qwb-0001", fixture_ref: "fx-evidence-001", description: "证据。" },
    { step: 7, title: "查看防御候选", path: "/defenses?request_id=inv-qwb-0001", fixture_ref: "fx-defense-001", description: "候选。" },
    { step: 8, title: "查看实验比较", path: "/experiments", fixture_ref: "fx-experiments-001", description: "实验。" },
    { step: 9, title: "生成报告", path: "/reports", fixture_ref: "fx-reports-001", description: "报告。" },
  ],
  scenarios: [
    {
      scenario_id: "sc-qwb-001",
      name: "多智能体供应链工具调用滥用审计",
      description: "演示场景。",
      risk_types: ["tool_abuse", "prompt_injection"],
    },
  ],
  scenarios_error: null,
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

describe("DemoCenterPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useAuthStore.getState().setSession({ role: "viewer", username: "viewer", authEnabled: false });
  });

  it("renders the full 9-step reproducible flow with fixture refs", async () => {
    mockFetch(overviewResponse);
    renderWithProviders(<DemoCenterPage />);
    expect(await screen.findByText("演示流程（9 步）")).toBeInTheDocument();
    expect(screen.getByText("选择演示场景")).toBeInTheDocument();
    expect(screen.getByText("查看 Agent 交互")).toBeInTheDocument();
    expect(screen.getByText("查看证据和限制")).toBeInTheDocument();
    expect(screen.getByText("查看防御候选")).toBeInTheDocument();
    expect(screen.getByText("生成报告")).toBeInTheDocument();
    expect((await screen.findAllByText("fx-graph-001")).length).toBeGreaterThan(0);
  });

  it("shows replay marker and scenario metadata", async () => {
    mockFetch(overviewResponse);
    renderWithProviders(<DemoCenterPage />);
    expect(await screen.findByText(/SYNTHETIC 演示/)).toBeInTheDocument();
    expect(screen.getByText("sc-qwb-001")).toBeInTheDocument();
    expect(screen.getByText("tool_abuse")).toBeInTheDocument();
  });

  it("keeps the flow even when scenarios are unavailable", async () => {
    mockFetch({
      meta: { data_mode: "unavailable" },
      flow: overviewResponse.flow,
      scenarios: [],
      scenarios_error: "API_UNAVAILABLE",
    });
    renderWithProviders(<DemoCenterPage />);
    expect(await screen.findByText("演示流程（9 步）")).toBeInTheDocument();
    expect(screen.getByText(/场景列表不可用，但流程导览仍可浏览/)).toBeInTheDocument();
  });
});
