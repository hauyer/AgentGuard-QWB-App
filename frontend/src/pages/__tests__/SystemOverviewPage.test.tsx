import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppLayout } from "../../components/layout/AppLayout";
import { SystemOverviewPage } from "../../pages/SystemOverviewPage";
import type { SystemStatus } from "../../types/system";

const liveStatus: SystemStatus = {
  app: { name: "agentguard-qwb-app", version: "0.1.0", status: "ok" },
  data_mode: "live",
  agentguard: {
    reachable: true,
    health: { status: "ok", service: "agentguard", version: "0.1.0-stub" },
    capabilities: {
      provider_id: "stub-warden",
      provider_version: "0.3.0",
      backend_mode: "synthetic",
      capabilities: { causal_audit: false },
      supported_target_types: ["message"],
      supported_operations: ["block"],
      limitations: [],
    },
  },
  warden: { status: "available", base_url: "http://stub-warden:9100" },
  features: [
    { name: "investigations.create", available: true, reason: null },
    { name: "defense.execute", available: false, reason: "unsupported" },
  ],
  unavailable_features: [
    { name: "defense.execute", available: false, reason: "unsupported" },
  ],
  generated_at: "2026-10-23T00:00:00Z",
};

const unavailableStatus: SystemStatus = {
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
      new Response(JSON.stringify(liveStatus), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    renderWithProviders(
      <Routes>
        <Route path="/" element={<SystemOverviewPage />} />
      </Routes>,
    );
    expect(await screen.findByText("LIVE")).toBeInTheDocument();
    expect(await screen.findByText("AgentGuard")).toBeInTheDocument();
    expect(await screen.findByText("WARDEN 内核")).toBeInTheDocument();
    expect(await screen.findByText("可用")).toBeInTheDocument();
  });

  it("renders explicit unavailable state without fabricating data", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(unavailableStatus), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    renderWithProviders(
      <Routes>
        <Route path="/" element={<SystemOverviewPage />} />
      </Routes>,
    );
    expect(await screen.findByText("UNAVAILABLE")).toBeInTheDocument();
    expect(await screen.findByText(/API_UNREACHABLE/)).toBeInTheDocument();
    expect(await screen.findByText(/Request ID：req-1/)).toBeInTheDocument();
  });

  it("shows a backend-unreachable error state instead of fake metrics", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("fetch failed"));
    renderWithProviders(
      <Routes>
        <Route path="/" element={<SystemOverviewPage />} />
      </Routes>,
    );
    expect(await screen.findByText("后端不可用")).toBeInTheDocument();
    expect(screen.queryByText("LIVE")).not.toBeInTheDocument();
  });
});

describe("AppLayout navigation", () => {
  it("renders the global navigation", () => {
    renderWithProviders(
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<SystemOverviewPage />} />
        </Route>
      </Routes>,
    );
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByText("系统总览")).toBeInTheDocument();
    expect(within(nav).getByText("安全调查")).toBeInTheDocument();
    expect(within(nav).getByText("交互图谱")).toBeInTheDocument();
    expect(within(nav).getByText("证据分析")).toBeInTheDocument();
    expect(within(nav).getByText("定向防御")).toBeInTheDocument();
    expect(within(nav).getByText("系统设置")).toBeInTheDocument();
  });
});
