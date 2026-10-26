import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MultiRoundReportPage } from "../MultiRoundReportPage";

const investigation = {
  request_id: "inv-live-42",
  scenario_id: "scenario-live-42",
  status: "completed",
  run_id: "run-live-42",
};

const loop = {
  loop_id: "loop-live-42",
  base_request_id: investigation.request_id,
  phase: "STOPPED",
  strategy: "risk_score",
  stop_reason: "BUDGET_EXHAUSTED",
};

const report = {
  schema_version: "1.0",
  data_mode: "live",
  generated_at: "2026-10-26T00:00:00+00:00",
  project: { project_id: 8, name: "project-live-8", status: "active" },
  investigation: { ...investigation, model_id: "model-live", runtime_id: "runtime-live" },
  loop: { ...loop, degradation: null },
  risk_analysis: {
    available: true,
    data: { findings: [{ finding_id: "finding-live-1", evidence_level: "observational", causal_validation: null }] },
    error_code: null,
  },
  decisions: {
    items: [{ decision_id: "decision-live-1", round_index: 1, strategy: "risk_score",
      selected_action_id: "read_evidence", result_status: "completed", new_evidence_count: 1,
      stop_reason: null }],
  },
  evidence_changes: { items: [{ evidence_id: "evidence-live-1", evidence_level: "observational" }] },
  budget: { budget: { max_actions: 3 }, metrics: { rounds_executed: 1 } },
  defense: { available: true, data: { candidates: [{ candidate_id: "candidate-1", status: "preview_only" }], execution_performed: false }, error_code: null },
  strategy_evaluation: null,
  strategy_evaluation_note: "没有可验证的关联。",
  data_sources: [{ name: "loop", source: "AgentGuard", available: true }],
  limitations: ["Test fixture only."],
};

function setupApi({ dataMode = "live", loops = [loop] }: { dataMode?: string; loops?: typeof loop[] } = {}) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("/api/investigations?") || url.endsWith("/api/investigations?limit=200&offset=0")) {
      return json({ meta: { data_mode: dataMode }, items: [investigation], count: 1, limit: 200, offset: 0 });
    }
    if (url.includes(`/api/investigations/${investigation.request_id}/loops`)) {
      return json({ meta: { data_mode: "live", ownership_verified: true }, items: loops, count: loops.length });
    }
    if (url.includes("/export.json")) {
      return new Response(JSON.stringify(report), { status: 200, headers: {
        "Content-Type": "application/json",
        "Content-Disposition": 'attachment; filename="investigation-report-inv-live-42-loop-live-42.json"',
      } });
    }
    if (url.includes("/export.pdf")) {
      return new Response(new Blob(["%PDF-stub"]), { status: 200, headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": 'attachment; filename="investigation-report-inv-live-42-loop-live-42.pdf"',
      } });
    }
    if (url.includes("/api/reports/investigations/")) return json({ meta: { data_mode: "live" }, report });
    throw new Error(`Unexpected request ${url}`);
  });
}

function json(value: unknown) {
  return new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
}

function renderPage(initialEntry = "/multi-round-report") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}><MultiRoundReportPage /></MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("MultiRoundReportPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("uses the selected verified live loop and renders real report fields", async () => {
    setupApi();
    renderPage("/multi-round-report?request_id=inv-live-42&loop_id=loop-live-42");

    expect(await screen.findByText("project-live-8")).toBeInTheDocument();
    expect(screen.getByText("inv-live-42")).toBeInTheDocument();
    expect(screen.getByText("loop-live-42")).toBeInTheDocument();
    expect(screen.getByText("decision-live-1")).toBeInTheDocument();
    expect(screen.getByText(/evidence-live-1/)).toBeInTheDocument();
    expect(screen.getByText("未执行")).toBeInTheDocument();
    expect(screen.queryByText("run-qwb-0001")).not.toBeInTheDocument();
  });

  it("does not request a report when an investigation has no verified loops", async () => {
    const fetchSpy = setupApi({ loops: [] });
    renderPage("/multi-round-report?request_id=inv-live-42");

    expect(await screen.findByText("该调查尚无可验证的 Loop 报告来源。")).toBeInTheDocument();
    expect(fetchSpy.mock.calls.some(([url]) => String(url).includes("/api/reports/investigations/"))).toBe(false);
  });

  it("does not mix recorded or synthetic investigations into the Live report flow", async () => {
    const fetchSpy = setupApi({ dataMode: "synthetic" });
    renderPage();

    expect(await screen.findByText(/Synthetic|synthetic/)).toBeInTheDocument();
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
    expect(fetchSpy.mock.calls[0][0]).toContain("/api/investigations?");
  });

  it("downloads the BFF JSON and PDF export endpoints", async () => {
    const fetchSpy = setupApi();
    const createObjectURL = vi.fn(() => "blob:report");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    renderPage("/multi-round-report?request_id=inv-live-42&loop_id=loop-live-42");
    expect(await screen.findByText("project-live-8")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "下载 JSON" }));
    await userEvent.click(screen.getByRole("button", { name: "导出 PDF" }));

    expect(fetchSpy.mock.calls.some(([url]) => String(url).endsWith("/export.json"))).toBe(true);
    expect(fetchSpy.mock.calls.some(([url]) => String(url).endsWith("/export.pdf"))).toBe(true);
    expect(createObjectURL).toHaveBeenCalledTimes(2);
    expect(click).toHaveBeenCalledTimes(2);
  });
});
