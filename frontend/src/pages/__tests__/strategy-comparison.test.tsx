import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StrategyComparisonPage } from "../StrategyComparisonPage";

const evaluations = [
  {
    evaluation_id: "eval-001",
    comparison_id: "comparison-001",
    report_artifact_id: "artifact-001",
    data_partition: "test",
    source_commit: null,
    executed_at: "2026-10-25T00:00:00+00:00",
    status: "available",
  },
  {
    evaluation_id: "eval-002",
    comparison_id: "comparison-002",
    report_artifact_id: "artifact-002",
    data_partition: "held_out_family",
    source_commit: "abc123",
    executed_at: "2026-10-25T01:00:00+00:00",
    status: "available",
  },
];

function detail(evaluationId: string) {
  const second = evaluationId === "eval-002";
  return {
    meta: { data_mode: "live", capability: "available", source_note: "AgentGuard persisted evaluation." },
    evaluation: {
      schema_version: "1.0",
      comparison_id: second ? "comparison-002" : "comparison-001",
      base_request_ids: ["inv-case-001"],
      strategies: ["risk_score"],
      repetitions: 1,
      data_partition: second ? "held_out_family" : "test",
      runs: [{
        schema_version: "1.0",
        experiment_id: "exp-001",
        run_label: "risk_score-1",
        strategy: "risk_score",
        repetition: 1,
        base_request_id: "inv-case-001",
        seed: null,
        budget: { max_rounds: 3, max_model_calls: 5, max_elapsed_seconds: 30 },
        execution_status: "completed",
        stop_reason: null,
        rounds_executed: 2,
        steps_to_first_evidence: null,
        effective_action_ratio: null,
        blocked_ratio: null,
        unsupported_ratio: null,
        redundant_action_count: 0,
        evidence_refs_collected: 0,
        hypotheses_raised: 0,
        model_calls_used: 0,
        elapsed_seconds: 1.25,
        strategy_degraded: false,
        loop_report_artifact_id: null,
        limitations: [],
        source_commit: null,
      }],
      aggregates: [{
        schema_version: "1.0",
        strategy: "risk_score",
        repetitions: 1,
        completed_runs: 1,
        blocked_runs: 0,
        mean_rounds: 2,
        mean_steps_to_first_evidence: null,
        mean_effective_action_ratio: null,
        mean_redundant_actions: null,
        mean_evidence_refs: null,
        mean_elapsed_seconds: 1.25,
        degradation_rate: null,
        notes: [],
      }],
      risk_identification_metrics: null,
      defense_effectiveness_metrics: null,
      limitations: ["Contract fixture only."],
      source_commit: second ? "abc123" : null,
      executed_at: "2026-10-25T00:00:00+00:00",
      report_artifact_id: second ? "artifact-002" : "artifact-001",
    },
  };
}

function mockEvaluationApi(items = evaluations) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("/research/strategy-evaluations/") && !url.includes("?")) {
      const evaluationId = url.split("/").pop() ?? "eval-001";
      return new Response(JSON.stringify(detail(decodeURIComponent(evaluationId))), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(JSON.stringify({
      meta: { data_mode: "live", capability: "available", source_note: "AgentGuard persisted evaluation." },
      schema_version: "1.0",
      items,
      count: items.length,
      offset: 0,
      limit: 100,
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  });
}

function renderPage(initialEntry = "/strategy-comparison") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}><StrategyComparisonPage /></MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("StrategyComparisonPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("loads the selected persisted detail after a page refresh and preserves null metrics", async () => {
    const fetchSpy = mockEvaluationApi();
    renderPage("/strategy-comparison?evaluation_id=eval-001");

    expect(await screen.findByText("comparison-001")).toBeInTheDocument();
    expect(screen.getByText("test", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getAllByText("1.25 秒").length).toBe(2);
    expect(screen.getAllByText("未提供").length).toBeGreaterThan(0);
    expect(screen.getByTestId("strategy-evaluation-run")).toHaveTextContent("未提供");
    expect(screen.queryByText("调查成本 (USD)")).not.toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/research/strategy-evaluations/eval-001"),
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("selects another evaluation and shows its matching comparison", async () => {
    mockEvaluationApi();
    renderPage();
    const select = await screen.findByTestId("strategy-evaluation-select");
    await userEvent.selectOptions(select, "eval-002");

    expect(await screen.findByText("comparison-002")).toBeInTheDocument();
    expect(screen.getByText("held_out_family", { selector: "dd" })).toBeInTheDocument();
  });

  it("shows an honest empty state without requesting details", async () => {
    const fetchSpy = mockEvaluationApi([]);
    renderPage();

    expect(await screen.findByText("当前没有已保存的策略评价。")).toBeInTheDocument();
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
    expect(fetchSpy.mock.calls[0][0]).toContain("/research/strategy-evaluations?");
  });
});
