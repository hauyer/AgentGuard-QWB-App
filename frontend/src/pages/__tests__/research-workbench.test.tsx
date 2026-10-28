import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ResearchWorkbenchPage } from "../../pages/ResearchWorkbenchPage";

function renderWithProviders(ui: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

const projectResponse = {
  items: [{ project_id: 7, name: "Protocol project", status: "active", investigation_count: 0 }],
  total: 1,
  count: 1,
  offset: 0,
  limit: 500,
};

const capabilityResponse = {
  meta: {
    data_mode: "synthetic",
    agentguard_commit: "d85aa97e1566e2c50816f2ade3129235266ec704",
    source_note: "RC5 capability response",
  },
  report: {
    schema_version: "1.0",
    backend_status: "blocked",
    source: "test stub",
    source_version: "stub",
    source_api_version: "1.1.0rc5",
    observed_at: "2026-10-28T10:00:00Z",
    capabilities: [{
      capability: "persistent_run",
      status: "SUPPORTED_BUT_BLOCKED",
      blockers: ["WARDEN_LIVE_GATE_BLOCKED"],
      source_version: "stub",
      source_api_version: "1.1.0rc5",
      advertised_by_warden: false,
      observed_at: "2026-10-28T10:00:00Z",
      evidence_refs: [],
      operation_id: null,
      contract_ref: null,
    }],
    limitations: ["Test stub only; no WARDEN run was performed."],
  },
};

const emptyStudies = {
  meta: { data_mode: "recorded", source_note: "Only local project links." },
  items: [],
  count: 0,
  total: 0,
  limit: 500,
  offset: 0,
  next_offset: null,
};

describe("ResearchWorkbenchPage", () => {
  it("labels synthetic capability state and displays the upstream blockers without fake studies", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = new URL(String(input), "http://qwb.test");
      if (url.pathname === "/api/projects") return Response.json(projectResponse);
      if (url.pathname === "/api/research/capabilities") return Response.json(capabilityResponse);
      if (url.pathname === "/api/projects/7/studies") return Response.json(emptyStudies);
      return new Response(JSON.stringify({ detail: { error: "NOT_FOUND", message: "not found" } }), { status: 404 });
    });

    renderWithProviders(<ResearchWorkbenchPage />);
    expect(await screen.findByText("persistent_run")).toBeInTheDocument();
    expect(screen.getAllByText("SYNTHETIC").length).toBeGreaterThan(0);
    expect(screen.getByText("WARDEN_LIVE_GATE_BLOCKED")).toBeInTheDocument();
    expect(screen.getByText("此项目还没有 Study")).toBeInTheDocument();
    expect(screen.getByText("执行与分析门控仍关闭")).toBeInTheDocument();
    expect(screen.queryByText("study-stub-0001")).not.toBeInTheDocument();
  });

  it("submits the chosen project and RC5 idempotency header, then refreshes its list", async () => {
    document.cookie = "qwb_csrf=csrf-test-token";
    let registered = false;
    let postRequest: RequestInit | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = new URL(String(input), "http://qwb.test");
      if (url.pathname === "/api/projects") return Response.json(projectResponse);
      if (url.pathname === "/api/research/capabilities") return Response.json(capabilityResponse);
      if (url.pathname === "/api/projects/7/studies" && init?.method === "POST") {
        registered = true;
        postRequest = init;
        return Response.json({
          replayed: false,
          submission: {
            study_id: "study-rc5-1",
            title: "Preregistered method comparison",
            track: "mechanism_testbed",
            status: "LINKED",
            study: null,
            registration_sha256: "a".repeat(64),
            request_id: "request-1",
            source: { mode: "recorded", origin_mode: "synthetic", agentguard_commit: "d85aa97", created_at: null },
            error_code: null,
            error_message: null,
          },
        }, { status: 201 });
      }
      if (url.pathname === "/api/projects/7/studies") return Response.json(registered ? {
        ...emptyStudies,
        items: [{
          study_id: "study-rc5-1", title: "Preregistered method comparison", track: "mechanism_testbed",
          status: "LINKED", study: null, registration_sha256: "a".repeat(64), request_id: "request-1",
          source: { mode: "recorded", origin_mode: "synthetic", agentguard_commit: "d85aa97", created_at: null },
          error_code: null, error_message: null,
        }],
        count: 1,
        total: 1,
      } : emptyStudies);
      return new Response(JSON.stringify({ detail: { error: "NOT_FOUND", message: "not found" } }), { status: 404 });
    });

    renderWithProviders(<ResearchWorkbenchPage />);
    await screen.findByText("此项目还没有 Study");
    const setField = (label: RegExp, value: string) =>
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    setField(/Study 标题/, "Preregistered method comparison");
    setField(/研究问题/, "Does a registered method change this outcome?");
    setField(/主要假设/, "The treatment arm changes the declared outcome.");
    setField(/主要结果变量/, "srr_itt");
    setField(/计划配对数/, "20");
    setField(/计划案例族数量/, "10");
    setField(/匹配变量/, "case_family");
    setField(/纳入条件/, "Records conform to the preregistered schema.");
    setField(/停止规则/, "Stop after all planned pairs resolve.");
    setField(/缺失数据规则/, "Report missing values without imputation.");
    setField(/实验臂定义 JSON/, JSON.stringify([
      { arm_id: "baseline", role: "baseline", method_id: "control", method_version: "1", parameter_sha256: "a".repeat(64) },
      { arm_id: "treatment", role: "treatment", method_id: "method-a", method_version: "1", parameter_sha256: "b".repeat(64) },
    ]));
    fireEvent.click(screen.getByRole("button", { name: "预览注册摘要" }));
    const preview = await screen.findByRole("region", { name: "不可变注册摘要" });
    expect(preview).toHaveTextContent("Preregistered method comparison");
    expect(preview).toHaveTextContent('"analysis_method": "clustered_paired"');
    fireEvent.click(screen.getByRole("button", { name: "确认并登记 Study" }));

    expect(await screen.findByText(/Study 已登记并绑定到当前项目/)).toBeInTheDocument();
    await waitFor(() => expect(registered).toBe(true));
    expect(postRequest?.method).toBe("POST");
    const headers = new Headers(postRequest?.headers);
    expect(headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/i);
    expect(headers.get("X-CSRF-Token")).toBe("csrf-test-token");
    expect(JSON.parse(String(postRequest?.body))).toMatchObject({
      title: "Preregistered method comparison",
      primary_outcome: "srr_itt",
      planned_pairs: 20,
      planned_case_families: 10,
      alpha: 0.05,
      seed: 7,
      arms: [
        { arm_id: "baseline", parameter_sha256: "a".repeat(64) },
        { arm_id: "treatment", parameter_sha256: "b".repeat(64) },
      ],
    });
    expect((await screen.findAllByText("study-rc5-1")).length).toBeGreaterThan(0);
  });
});
