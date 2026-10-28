import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, MemoryRouter, Route, Routes, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppLayout } from "../../components/layout/AppLayout";
import { SystemOverviewPage } from "../../pages/SystemOverviewPage";
import { useAuthStore } from "../../stores/auth-store";
import type { DashboardResponse } from "../../types/dashboard";
import type { SystemStatus } from "../../types/system";

const liveSystem: SystemStatus = {
  app: { name: "agentguard-qwb-app", version: "0.1.0", status: "ok" },
  data_mode: "live",
  agentguard: {
    reachable: true,
    health: { status: "ok", service: "agentguard", version: "0.1.0-stub" },
    capabilities: {
      provider_id: "stub-warden",
      provider_version: "0.3.0",
      backend_mode: "synthetic",
      capabilities: { causal_audit: true, probe_training: false },
      supported_target_types: ["message"],
      supported_operations: ["block"],
      limitations: [],
    },
  },
  warden: { status: "available", base_url: "http://stub-warden:9100" },
  runtime: { status: "blocked", reason: "COMPONENT_UNAVAILABLE:agent.runtime" },
  probe_sae: { status: "unknown", reason: "AgentGuard readiness did not report this layer." },
  threat_contracts: { status: "unknown", blockers: ["NO_THREAT_CONTRACTS"] },
  artifacts: { status: "unknown", reason: "No verified artifact status." },
  features: [
    { name: "investigations.create", available: true, reason: null },
    { name: "defense.execute", available: false, reason: "unsupported" },
  ],
  unavailable_features: [
    { name: "defense.execute", available: false, reason: "unsupported" },
  ],
  generated_at: "2026-10-23T00:00:00Z",
};

const liveDashboard: DashboardResponse = {
  system: liveSystem,
  investigation_summary: {
    available: true,
    sample_based: true,
    total: 6,
    running: 1,
    completed: 2,
    blocked: 1,
    failed: 1,
    pending: 1,
    recent_request_id: "inv-qwb-0001",
    recent_status: "completed",
  },
  evidence_summary: {
    available: true,
    sample_based: true,
    by_level: { observational: 2, interventional: 1, causal_validated: 1 },
    by_verification: { verified: 2, unverified: 1 },
    recent_count: 4,
  },
  policy_summary: {
    available: true,
    sample_based: true,
    pending_approval: 2,
    approved: 1,
    unsupported: 3,
    verified_historical: 1,
  },
  dependency_blockers: [
    { id: "QWB-INT-001", title: "消息级交互图谱 API 缺失", impact: "交互图谱页在 Live 模式不可用", status: "open" },
  ],
  audit_capabilities: [{ name: "causal_audit", enabled: true, note: "因果审计" }],
  meta: { data_mode: "live" },
};

const unavailableSystem: SystemStatus = {
  app: { name: "agentguard-qwb-app", version: "0.1.0", status: "ok" },
  data_mode: "unavailable",
  agentguard: {
    reachable: false,
    error: { code: "API_UNREACHABLE", message: "connection refused", request_id: "req-1" },
  },
  warden: { status: "unavailable", reason: "AgentGuard unreachable" },
  features: [{ name: "system.status", available: false, reason: "AgentGuard unreachable" }],
  unavailable_features: [
    { name: "system.status", available: false, reason: "AgentGuard unreachable" },
  ],
  generated_at: "2026-10-23T00:00:00Z",
};

const unavailableDashboard: DashboardResponse = {
  system: unavailableSystem,
  investigation_summary: { available: false, sample_based: false, error: "AgentGuard unreachable and demo mode not enabled" },
  evidence_summary: { available: false, sample_based: false, by_level: {}, by_verification: {}, error: "unreachable" },
  policy_summary: { available: false, sample_based: false, error: "unreachable" },
  dependency_blockers: [],
  audit_capabilities: [],
  meta: { data_mode: "unavailable" },
};

const syntheticDashboard: DashboardResponse = {
  system: { ...liveSystem, data_mode: "synthetic" },
  investigation_summary: { available: true, sample_based: false, total: 6, completed: 2, running: 1 },
  evidence_summary: {
    available: true,
    sample_based: false,
    by_level: { synthetic: 1, observational: 2, causal_validated: 1 },
    by_verification: { verified: 1, unverified: 3 },
    recent_count: 4,
  },
  policy_summary: { available: true, sample_based: false, pending_approval: 2, approved: 1, unsupported: 2, verified_historical: 1 },
  dependency_blockers: [],
  audit_capabilities: [],
  meta: {
    data_mode: "synthetic",
    fixture_id: "fx-inv-001",
    source: "sanitised recording",
    sanitized: true,
    not_provable: ["调查状态不代表真实 WARDEN 运行。"],
  },
};

function renderWithProviders(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SystemOverviewPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders live status from the BFF", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(liveDashboard), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    renderWithProviders(
      <Routes>
        <Route path="/" element={<SystemOverviewPage />} />
      </Routes>,
    );
    expect(await screen.findByText("AgentGuard")).toBeInTheDocument();
    expect(await screen.findByText("WARDEN 内核")).toBeInTheDocument();
    expect(await screen.findByText("Probe / SAE")).toBeInTheDocument();
    expect(screen.getByText("COMPONENT_UNAVAILABLE:agent.runtime")).toBeInTheDocument();
    expect(screen.getByText("NO_THREAT_CONTRACTS")).toBeInTheDocument();
    expect(await screen.findByText("可用")).toBeInTheDocument();
    expect(await screen.findByText("调查概况")).toBeInTheDocument();
    expect(await screen.findByText("6")).toBeInTheDocument();
    expect(await screen.findByText(/最近一次调查：inv-qwb-0001/)).toBeInTheDocument();
  });

  it("renders explicit unavailable state without fabricating data", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(unavailableDashboard), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    renderWithProviders(
      <Routes>
        <Route path="/" element={<SystemOverviewPage />} />
      </Routes>,
    );
    expect(await screen.findByText(/API_UNREACHABLE/)).toBeInTheDocument();
    expect(await screen.findByText(/Request ID：req-1/)).toBeInTheDocument();
    // Metrics must not show fabricated zeros
    expect(screen.getAllByText("不可用").length).toBeGreaterThan(0);
    expect(screen.queryByText("6")).not.toBeInTheDocument();
  });

  it("labels synthetic demo data as replay, not live", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(syntheticDashboard), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    renderWithProviders(
      <Routes>
        <Route path="/" element={<SystemOverviewPage />} />
      </Routes>,
    );
    expect(await screen.findByText(/SYNTHETIC 演示/)).toBeInTheDocument();
    expect(await screen.findByText("fx-inv-001")).toBeInTheDocument();
    expect(screen.queryByText("LIVE")).not.toBeInTheDocument();
  });

  it("shows a backend-unreachable error state instead of fake metrics", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("fetch failed"));
    renderWithProviders(
      <Routes>
        <Route path="/" element={<SystemOverviewPage />} />
      </Routes>,
    );
    expect(await screen.findByText(/fetch failed/)).toBeInTheDocument();
    expect(screen.queryByText("调查概况")).not.toBeInTheDocument();
  });
});

describe("AppLayout navigation", () => {
  it("renders the global navigation", () => {
    useAuthStore.getState().clearSession();
    const router = createMemoryRouter([
      {
        path: "/",
        element: <AppLayout />,
        children: [{ index: true, element: <SystemOverviewPage />, handle: { title: "系统总览" } }],
      },
    ]);
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByText("系统总览")).toBeInTheDocument();
    expect(within(nav).getByText("安全调查")).toBeInTheDocument();
    expect(within(nav).getByText("研究工作台")).toBeInTheDocument();
    expect(within(nav).getByText("交互图谱")).toBeInTheDocument();
    expect(within(nav).getByText("证据分析")).toBeInTheDocument();
    expect(within(nav).getByText("定向防御")).toBeInTheDocument();
    expect(within(nav).getByText("系统设置")).toBeInTheDocument();
  });
});
