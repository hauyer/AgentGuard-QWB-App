import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InvestigationWorkspacePage } from "../../pages/InvestigationWorkspacePage";

const detailPayload = {
  meta: { data_mode: "synthetic", fixture_id: "fx-investigations-001" },
  investigation: {
    request_id: "inv-stub-0001",
    status: "completed",
    workflow_status: "completed",
    mode: "detection",
    scenario_id: "sc-qwb-001",
    model_id: "m",
    runtime_id: "rt",
    run_id: "run-stub-0001",
  },
};

const timelinePayload = {
  meta: { data_mode: "live", timeline_source: "upstream", run_id: "run-stub-0001" },
  events: [
    { step: "plan_submitted", label: "计划提交", status: "completed", at: "2026-10-24T00:00:00Z" },
  ],
};

const graphPayload = {
  meta: { data_mode: "live", capability: "available", source: "agentguard-interaction-graph" },
  graph: {
    scenario_id: "sc-qwb-001",
    nodes: [
      { id: "agent-a", type: "agent", label: "agent-a", risk: "unknown", source_id: "agent-a" },
      { id: "tool-1", type: "tool", label: "tool-1", risk: "unknown", source_id: "tool-1" },
    ],
    edges: [
      {
        id: "msg-0001",
        source: "agent-a",
        target: "tool-1",
        type: "message",
        message_id: "msg-0001",
        risk: "unknown",
        source_id: "msg-0001",
      },
    ],
    candidate_paths: [],
    upstream_available: true,
  },
};

const reportPayload = {
  meta: { data_mode: "live" },
  report: {
    run_id: "run-stub-0001",
    status: "completed",
    findings: [
      {
        finding_id: "f-1",
        severity: "high",
        risk_type: "tool_abuse",
        summary: "可疑工具调用序列",
        evidence_ids: ["ev-1"],
      },
    ],
  },
};

function mockFetch(routes: Record<string, unknown>) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    for (const [pattern, value] of Object.entries(routes)) {
      if (url.includes(pattern)) {
        return new Response(JSON.stringify(value), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
    }
    return new Response(JSON.stringify({ detail: { error: "NOT_FOUND", message: "mock 未命中" } }), { status: 404 });
  });
}

function renderWithProviders(ui: ReactNode, initialEntries: string[] = ["/"]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("InvestigationWorkspacePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows status, upstream timeline source, graph edges and real IDs", async () => {
    mockFetch({
      // order matters: the timeline URL contains the detail URL as a prefix
      "/timeline": timelinePayload,
      "/investigations/inv-stub-0001": detailPayload,
      "/interaction-graph": graphPayload,
      "/reports/run-stub-0001": reportPayload,
    });
    renderWithProviders(
      <Routes>
        <Route path="/investigations/:requestId/workspace" element={<InvestigationWorkspacePage />} />
      </Routes>,
      ["/investigations/inv-stub-0001/workspace"],
    );
    expect(await screen.findByText("调查工作区")).toBeInTheDocument();
    expect(await screen.findByText("来自 AgentGuard 持久化事件")).toBeInTheDocument();
    // edges render with provenance ids
    expect(await screen.findByText(/agent-a → tool-1/)).toBeInTheDocument();
    // findings from the real report payload
    expect(await screen.findByText("可疑工具调用序列")).toBeInTheDocument();
    expect(screen.getByText("f-1")).toBeInTheDocument();
  });

  it("shows the honest empty-graph state when upstream has no data", async () => {
    mockFetch({
      "/investigations/inv-stub-0001": detailPayload,
      "/timeline": timelinePayload,
      "/interaction-graph": {
        meta: { data_mode: "live", capability: "upstream_no_data" },
        graph: {
          nodes: [], edges: [], candidate_paths: [],
          upstream_available: false,
          not_provable: ["GRAPH_SOURCE_UNAVAILABLE: no message metadata recorded."],
        },
      },
      "/reports/run-stub-0001": { meta: { data_mode: "live" }, report: { run_id: "run-stub-0001", findings: [] } },
    });
    renderWithProviders(
      <Routes>
        <Route path="/investigations/:requestId/workspace" element={<InvestigationWorkspacePage />} />
      </Routes>,
      ["/investigations/inv-stub-0001/workspace"],
    );
    expect(await screen.findByText("当前上游没有可展示的图谱数据。")).toBeInTheDocument();
    expect(await screen.findByText(/GRAPH_SOURCE_UNAVAILABLE/)).toBeInTheDocument();
    expect(await screen.findByText("报告未包含风险发现（真实空集）。")).toBeInTheDocument();
  });
});
