import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InteractionGraphPage } from "../../pages/InteractionGraphPage";
import type { GraphResponse } from "../../types/graph";

const graphResponse: GraphResponse = {
  meta: {
    data_mode: "synthetic",
    fixture_id: "fx-graph-001",
    source: "sanitised recording",
    sanitized: true,
    not_provable: ["图谱边不代表真实消息级传输，仅用于演示候选路径与证据引用对应。"],
  },
  graph: {
    scenario_id: "sc-qwb-001",
    nodes: [
      { id: "agent-a", type: "agent", label: "Agent A（采购处理）", risk: "high", timestamp: "2026-10-20T09:12:00+08:00", source_id: "agent-a" },
      { id: "agent-b", type: "agent", label: "Agent B（文档解析）", risk: "medium", timestamp: "2026-10-20T09:12:01+08:00", source_id: "agent-b" },
      { id: "tool-settlement", type: "tool", label: "结算工具（内部）", risk: "high", timestamp: "2026-10-20T09:12:20+08:00", source_id: "tool:settlement" },
      { id: "tool-whitelist", type: "tool", label: "工具白名单网关", risk: "low", timestamp: "2026-10-20T09:12:20+08:00", source_id: "tool:whitelist" },
      { id: "model-m1", type: "model", label: "模型 agent-suite-2.1", risk: "low", timestamp: "2026-10-20T09:12:00+08:00", source_id: "model:agent-suite-2.1" },
      { id: "inv-01", type: "invocation", label: "inv-01 结算调用", risk: "high", timestamp: "2026-10-20T09:12:20+08:00", source_id: "inv-01" },
      { id: "inv-02", type: "invocation", label: "inv-02 白名单查询", risk: "low", timestamp: "2026-10-20T09:12:18+08:00", source_id: "inv-02" },
      { id: "res-ext", type: "external_resource", label: "外部供应商文档", risk: "medium", timestamp: "2026-10-20T09:12:05+08:00", source_id: "res:vendor-doc" },
    ],
    edges: [
      { id: "e-01", source: "res-ext", target: "agent-b", type: "message", message_id: "msg-041", risk: "medium", timestamp: "2026-10-20T09:12:05+08:00", source_id: "msg-041", metadata: { role: "tool_result", summary: "供应商文档解析结果（含注入特征）" } },
      { id: "e-02", source: "agent-b", target: "agent-a", type: "message", message_id: "msg-042", risk: "high", timestamp: "2026-10-20T09:12:06+08:00", source_id: "msg-042", metadata: { role: "agent_message", summary: "转述文档中的结算指令" } },
      { id: "e-03", source: "agent-a", target: "tool-whitelist", type: "invocation", message_id: "inv-02", risk: "low", timestamp: "2026-10-20T09:12:18+08:00", source_id: "inv-02", metadata: { tool: "whitelist.query" } },
      { id: "e-04", source: "tool-whitelist", target: "agent-a", type: "result", message_id: "res-02", risk: "low", timestamp: "2026-10-20T09:12:19+08:00", source_id: "res-02", metadata: { summary: "白名单查询结果" } },
      { id: "e-05", source: "agent-a", target: "tool-settlement", type: "invocation", message_id: "inv-01", risk: "high", timestamp: "2026-10-20T09:12:20+08:00", source_id: "inv-01", metadata: { tool: "settlement.execute", summary: "越权调用" } },
      { id: "e-06", source: "model-m1", target: "agent-a", type: "invocation", message_id: "inf-01", risk: "low", timestamp: "2026-10-20T09:12:00+08:00", source_id: "inf-01", metadata: { summary: "模型推理" } },
    ],
    candidate_paths: [
      { id: "path-qwb-001", label: "注入诱导越权结算路径", node_ids: ["res-ext", "agent-b", "agent-a", "tool-settlement"], edge_ids: ["e-01", "e-02", "e-05"], evidence_refs: ["ev-qwb-0001", "ev-qwb-0002"], risk: "high" },
      { id: "path-qwb-002", label: "白名单绕过尝试路径", node_ids: ["agent-a", "tool-whitelist", "tool-settlement"], edge_ids: ["e-03", "e-04", "e-05"], evidence_refs: ["ev-qwb-0003"], risk: "medium" },
    ],
  },
};

function mockGraphFetch() {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(graphResponse), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
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

describe("InteractionGraphPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders graph nodes and edges from the fixture with replay marker", async () => {
    mockGraphFetch();
    renderWithProviders(<InteractionGraphPage />);
    expect(await screen.findByText(/RECORDED 回放|SYNTHETIC 演示/)).toBeInTheDocument();
    expect(await screen.findByText("fx-graph-001")).toBeInTheDocument();
    // node labels are rendered in the flow canvas
    expect(screen.getAllByText("Agent A（采购处理）").length).toBeGreaterThan(0);
    expect(screen.getAllByText("结算工具（内部）").length).toBeGreaterThan(0);
    // candidate path chips
    expect(screen.getByRole("button", { name: "注入诱导越权结算路径" })).toBeInTheDocument();
    // not-provable disclaimer
    expect(screen.getByText(/图谱边不代表真实消息级传输/)).toBeInTheDocument();
  });

  it("shows candidate path details with evidence refs when selected", async () => {
    mockGraphFetch();
    renderWithProviders(<InteractionGraphPage />);
    await screen.findByText("fx-graph-001");
    await userEvent.click(screen.getByRole("button", { name: "白名单绕过尝试路径" }));
    expect(await screen.findByText("候选路径详情")).toBeInTheDocument();
    expect(screen.getByText(/ev-qwb-0003/)).toBeInTheDocument();
    expect(screen.getByText(/agent-a → tool-whitelist → tool-settlement/)).toBeInTheDocument();
  });

  it("shows explicit live-capability-unavailable error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: { error: "GRAPH_API_UNAVAILABLE", message: "AgentGuard 当前公共 API 未提供消息级交互图谱（QWB-INT-001）" },
        }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      ),
    );
    renderWithProviders(<InteractionGraphPage />);
    expect(await screen.findByText(/GRAPH_API_UNAVAILABLE/)).toBeInTheDocument();
    expect(screen.getByText(/QWB-INT-001/)).toBeInTheDocument();
  });
});
