import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { InvestigationJournalPage } from "../../pages/InvestigationJournalPage";

function renderWithProviders(ui: ReactNode, initialEntries: string[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("InvestigationJournalPage", () => {
  it("loads two real rounds, evidence changes and budget from the selected Loop", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      let payload: unknown;
      if (url.endsWith("/investigation-loops/loop-real-1")) {
        payload = {
          meta: { data_mode: "live", source: "agentguard" },
          loop_id: "loop-real-1",
          base_request_id: "inv-real-1",
          phase: "COMPLETED",
          strategy: "risk_score",
          stop_reason: "BUDGET_EXHAUSTED",
          degradation: null,
        };
      } else if (url.endsWith("/decisions")) {
        payload = {
          meta: { data_mode: "live" },
          items: [
            { decision_id: "d1", round_index: 1, phase: "RUNNING", strategy: "risk_score", candidate_actions: ["a1"], selected_action_id: "a1", selection_reason: null, evidence_refs: ["e1"], evidence_refs_before: [], evidence_refs_after: ["e1"], new_evidence_count: 1, cost_estimate: null, actual_cost: null, remaining_budget: null, result_status: "completed", new_evidence: true, stop_reason: null },
            { decision_id: "d2", round_index: 2, phase: "COMPLETED", strategy: "risk_score", candidate_actions: ["a2"], selected_action_id: "a2", selection_reason: null, evidence_refs: ["e2"], evidence_refs_before: ["e1"], evidence_refs_after: ["e1", "e2"], new_evidence_count: 1, cost_estimate: null, actual_cost: null, remaining_budget: null, result_status: "completed", new_evidence: true, stop_reason: "BUDGET_EXHAUSTED" },
          ],
        };
      } else if (url.endsWith("/evidence-changes")) {
        payload = {
          meta: { data_mode: "live" }, schema_version: "1.0", loop_id: "loop-real-1", count: 2,
          limitations: [], items: [
            { decision_id: "d1", round_index: 1, new_evidence_count: 1, evidence_refs_after: ["e1"] },
            { decision_id: "d2", round_index: 2, new_evidence_count: 1, evidence_refs_after: ["e1", "e2"] },
          ],
        };
      } else if (url.endsWith("/budget")) {
        payload = {
          meta: { data_mode: "live" }, loop_id: "loop-real-1",
          budget: { max_actions: 8, max_seconds: 300, max_model_calls: 4 },
          metrics: { rounds_executed: 2, elapsed_seconds: 12.5, model_calls_used: 1, steps_to_first_evidence: 1, effective_action_ratio: null },
          remaining: { actions_left: 6, seconds_left: 287.5, model_calls_left: 3 },
        };
      } else {
        return new Response(JSON.stringify({ detail: { error: "NOT_FOUND", message: "missing" } }), { status: 404 });
      }
      return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    renderWithProviders(
      <Routes><Route path="/investigation-journal" element={<InvestigationJournalPage />} /></Routes>,
      ["/investigation-journal?loop_id=loop-real-1"],
    );

    expect(await screen.findByText("loop-real-1")).toBeInTheDocument();
    expect(screen.getByText("Round 1")).toBeInTheDocument();
    expect(screen.getByText("Round 2")).toBeInTheDocument();
    expect(screen.getAllByText("e1").length).toBeGreaterThan(0);
    expect(screen.getByText("e2")).toBeInTheDocument();
    expect(document.body.textContent).toContain("已用时间：12.5s/300s");
    expect(screen.getByText(/数据源：LIVE/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/api/investigation-loops/loop-real-1"))).toBe(true);
  });

  it("starts from investigation navigation instead of free-text loop ids", () => {
    renderWithProviders(
      <Routes><Route path="/investigation-journal" element={<InvestigationJournalPage />} /></Routes>,
      ["/investigation-journal"],
    );
    expect(screen.getByText(/页面不接受手动 loop_id 输入/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "前往项目列表 →" })).toHaveAttribute("href", "/projects");
  });
});
