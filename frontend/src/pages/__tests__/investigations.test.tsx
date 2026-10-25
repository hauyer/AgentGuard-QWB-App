import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "../../stores/auth-store";
import { CreateInvestigationPage } from "../../pages/CreateInvestigationPage";
import { InvestigationDetailPage } from "../../pages/InvestigationDetailPage";
import { InvestigationsListPage } from "../../pages/InvestigationsListPage";
import type { MetaInfo } from "../../types/dashboard";

const recordedMeta: MetaInfo = {
  data_mode: "recorded",
  fixture_id: "fx-inv-001",
  source: "sanitised recording",
  sanitized: true,
  not_provable: ["调查状态不代表真实 WARDEN 运行。"],
};

const listResponse = {
  meta: recordedMeta,
  items: [
    {
      request_id: "inv-qwb-0001",
      scenario_id: "sc-qwb-001",
      mode: "causal_audit",
      status: "completed",
      created_at: "2026-10-20T10:00:00+00:00",
      run_id: "run-qwb-0001",
    },
    {
      request_id: "inv-qwb-0002",
      scenario_id: "sc-qwb-001",
      mode: "causal_audit",
      status: "running",
      created_at: "2026-10-21T09:00:00+00:00",
      run_id: "run-qwb-0002",
    },
    {
      request_id: "inv-qwb-0003",
      scenario_id: "sc-qwb-002",
      mode: "detection",
      status: "blocked",
      created_at: "2026-10-22T08:00:00+00:00",
      error_code: "PLAN_BLOCKED",
    },
  ],
  count: 3,
  offset: 0,
  limit: 10,
  total: 3,
  next_offset: null,
};

const detailResponse = {
  meta: recordedMeta,
  investigation: {
    request_id: "inv-qwb-0001",
    contract_id: "contract-qwb-001",
    model_id: "agent-suite-2.1",
    runtime_id: "runtime-stub-1",
    mode: "causal_audit",
    status: "completed",
    workflow_status: "completed",
    created_at: "2026-10-20T10:00:00+00:00",
    updated_at: "2026-10-20T10:05:00+00:00",
    plan_id: "plan-qwb-0001",
    run_id: "run-qwb-0001",
    experiment_id: "exp-qwb-001",
    result: { risk_findings: 2, evidence_refs: ["ev-qwb-0001", "ev-qwb-0003"] },
    follow_up: ["扩大采集范围覆盖 prompt_injection 场景"],
    allows_defense_candidates: true,
  },
};

const timelineResponse = {
  meta: recordedMeta,
  events: [
    { step: "created", label: "调查创建", status: "completed", at: "2026-10-20T10:00:00+00:00" },
    { step: "validated", label: "请求验证", status: "completed", at: "2026-10-20T10:00:01+00:00" },
    { step: "capabilities", label: "能力检查", status: "completed", at: "2026-10-20T10:00:02+00:00" },
    { step: "planned", label: "审计计划", status: "completed", at: "2026-10-20T10:00:03+00:00", detail: "计划 plan-qwb-0001" },
    { step: "submitted", label: "运行提交", status: "completed", at: "2026-10-20T10:00:04+00:00", detail: "运行 run-qwb-0001" },
    { step: "running", label: "运行中", status: "completed", at: "2026-10-20T10:00:05+00:00" },
    { step: "evidence", label: "证据生成", status: "completed", at: "2026-10-20T10:04:00+00:00" },
    { step: "completed", label: "调查完成", status: "completed", at: "2026-10-20T10:05:00+00:00" },
  ],
};

const wardenUnavailable = {
  detail: { error: "WARDEN_NOT_CONFIGURED", message: "WARDEN 尚未配置，无法创建审计运行" },
};

const scenariosResponse = {
  items: [{ scenario_id: "sc-qwb-001", name: "多智能体供应链工具调用滥用审计", risk_types: ["tool_abuse"] }],
};

const systemStatusResponse = {
  app: { name: "agentguard-qwb-app", version: "0.1.0", status: "ok" },
  data_mode: "recorded",
  agentguard: { reachable: false, error: { code: "API_UNREACHABLE", message: "unreachable", request_id: null } },
  warden: { status: "unavailable", reason: "demo mode" },
  capabilities: {
    provider_id: null,
    provider_version: null,
    backend_mode: "demo",
    capabilities: { probe_rest: false, sae_rest: false },
    supported_target_types: [],
    supported_operations: [],
    limitations: [],
  },
  features: [],
  unavailable_features: [],
  generated_at: "2026-10-23T00:00:00Z",
};

function mockFetch(routes: Record<string, unknown>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
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

describe("InvestigationsListPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders investigations with demo replay banner and pagination", async () => {
    mockFetch({ "/investigations?" : listResponse });
    renderWithProviders(
      <Routes>
        <Route path="/" element={<InvestigationsListPage />} />
      </Routes>,
    );
    expect(await screen.findByText("inv-qwb-0001")).toBeInTheDocument();
    expect(screen.getByText("inv-qwb-0002")).toBeInTheDocument();
    expect(screen.getByText(/RECORDED 回放/)).toBeInTheDocument();
    expect(screen.getByText("fx-inv-001")).toBeInTheDocument();
    expect(screen.getByText(/共 3 条/)).toBeInTheDocument();
  });

  it("filters by status through URL parameters", async () => {
    const fetchMock = mockFetch({ "/investigations?" : listResponse });
    renderWithProviders(
      <Routes>
        <Route path="/" element={<InvestigationsListPage />} />
      </Routes>,
    );
    await screen.findByText("inv-qwb-0001");
    const blockedChip = screen.getByRole("button", { name: "阻塞" });
    await userEvent.click(blockedChip);
    const lastCall = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
    expect(String(lastCall[0])).toContain("status=blocked");
  });

  it("shows a create button only for analyst or above", async () => {
    mockFetch({ "/investigations?" : listResponse });
    useAuthStore.setState({ role: "analyst", authEnabled: true, status: "ready", username: "analyst" });
    renderWithProviders(
      <Routes>
        <Route path="/" element={<InvestigationsListPage />} />
      </Routes>,
    );
    expect(await screen.findByRole("link", { name: "新建调查" })).toBeInTheDocument();
  });

  it("hides the create button for viewer", async () => {
    mockFetch({ "/investigations?" : listResponse });
    useAuthStore.setState({ role: "viewer", authEnabled: true, status: "ready", username: "viewer" });
    renderWithProviders(
      <Routes>
        <Route path="/" element={<InvestigationsListPage />} />
      </Routes>,
    );
    await screen.findByText("inv-qwb-0001");
    expect(screen.queryByRole("link", { name: "新建调查" })).not.toBeInTheDocument();
  });
});

describe("InvestigationDetailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders status, timeline and result, recovering by request id", async () => {
    mockFetch({ "/timeline" : timelineResponse, "/investigations/" : detailResponse });
    renderWithProviders(
      <Routes>
        <Route path="/investigations/:requestId" element={<InvestigationDetailPage />} />
      </Routes>,
      ["/investigations/inv-qwb-0001"],
    );
    expect(await screen.findByText("inv-qwb-0001")).toBeInTheDocument();
    expect(screen.getByText("run-qwb-0001")).toBeInTheDocument();
    expect(screen.getByText("调查时间线")).toBeInTheDocument();
    expect(screen.getByText("调查完成")).toBeInTheDocument();
    expect(screen.getByText(/Demo、Recorded 与 Synthetic 数据不会调用真实 Operator API/)).toBeInTheDocument();
    expect(screen.getByText("计划 plan-qwb-0001")).toBeInTheDocument();
    // result JSON is collapsed by default; expand it before asserting content
    await userEvent.click(screen.getByRole("button", { name: /展开/ }));
    expect(screen.getByText(/risk_findings/)).toBeInTheDocument();
    // the timeline shows only confirmed steps (no "未确认" for a completed run)
    expect(screen.queryByText(/未确认/)).not.toBeInTheDocument();
  });

  it("marks unconfirmed timeline steps as pending", async () => {
    mockFetch({
      "/timeline": {
        meta: recordedMeta,
        events: [
          { step: "created", label: "调查创建", status: "completed", at: "2026-10-21T09:00:00+00:00" },
          { step: "validated", label: "请求验证", status: "pending" },
          { step: "completed", label: "调查完成", status: "pending" },
        ],
      },
      "/investigations/": {
        meta: recordedMeta,
        investigation: { request_id: "inv-qwb-0002", mode: "causal_audit", status: "running", run_id: "run-qwb-0002" },
      },
    });
    renderWithProviders(
      <Routes>
        <Route path="/investigations/:requestId" element={<InvestigationDetailPage />} />
      </Routes>,
      ["/investigations/inv-qwb-0002"],
    );
    expect(await screen.findByText("请求验证")).toBeInTheDocument();
    expect(screen.getAllByText(/未确认/).length).toBeGreaterThan(0);
  });

  it("shows an explicit WARDEN-unavailable error with the error code", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      return new Response(JSON.stringify(wardenUnavailable), { status: 503, headers: { "Content-Type": "application/json" } });
    });
    renderWithProviders(
      <Routes>
        <Route path="/investigations/:requestId" element={<InvestigationDetailPage />} />
      </Routes>,
      ["/investigations/inv-nope"],
    );
    expect(await screen.findByText(/WARDEN_NOT_CONFIGURED/)).toBeInTheDocument();
    expect(screen.getByText(/WARDEN 尚未配置/)).toBeInTheDocument();
  });
});

describe("CreateInvestigationPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useAuthStore.setState({ role: "analyst", authEnabled: true, status: "ready", username: "analyst" });
  });

  it("blocks submit until the typed contract is complete", async () => {
    mockFetch({ "/system/status": systemStatusResponse, "/scenarios": scenariosResponse });
    renderWithProviders(
      <Routes>
        <Route path="/new" element={<CreateInvestigationPage />} />
      </Routes>,
      ["/new"],
    );
    const submit = await screen.findByRole("button", { name: "提交调查" });
    expect(submit).toBeDisabled();
    const contract = screen.getByPlaceholderText("contract-qwb-001");
    await userEvent.type(contract, "contract-qwb-001");
    expect(submit).toBeDisabled(); // model/runtime still missing
  });

  it("submits a typed payload to the BFF on a complete form", async () => {
    mockFetch({ "/system/status": systemStatusResponse, "/scenarios": scenariosResponse });
    renderWithProviders(
      <Routes>
        <Route path="/new" element={<CreateInvestigationPage />} />
      </Routes>,
      ["/new"],
    );
    await userEvent.type(await screen.findByPlaceholderText("contract-qwb-001"), "contract-qwb-001");
    await userEvent.type(screen.getByPlaceholderText("agent-suite-2.1"), "agent-suite-2.1");
    await userEvent.type(screen.getByPlaceholderText("runtime-stub-1"), "runtime-stub-1");
    await userEvent.type(screen.getByPlaceholderText("target_id（必填）"), "agent-a");
    const submit = screen.getByRole("button", { name: "提交调查" });
    expect(submit).not.toBeDisabled();

    const postMock = mockFetch({
      "/investigations/inv": { meta: recordedMeta, investigation: detailResponse.investigation },
      "/investigations": { meta: recordedMeta, created: detailResponse.investigation },
      "/timeline": timelineResponse,
    });
    await userEvent.click(submit);

    const postCall = postMock.mock.calls.find(
      (call) =>
        String(call[0]).includes("/investigations") &&
        String((call[1] as RequestInit | undefined)?.method ?? "").toUpperCase() === "POST",
    );
    expect(postCall).toBeDefined();
    const postArgs = postCall as unknown as [RequestInfo, RequestInit | undefined];
    const body = JSON.parse(String(postArgs[1]?.body)) as Record<string, unknown>;
    expect(body.contract_id).toBe("contract-qwb-001");
    expect(body.model_id).toBe("agent-suite-2.1");
    expect(body.runtime_id).toBe("runtime-stub-1");
    expect(body.mode).toBe("causal_audit");
    expect(body.capture_targets).toEqual([expect.objectContaining({ target_id: "agent-a" })]);
    expect(body).not.toHaveProperty("request_id"); // BFF assigns the request id
  });

  it("gates creation behind the analyst role", async () => {
    useAuthStore.setState({ role: "viewer", authEnabled: true, status: "ready", username: "viewer" });
    mockFetch({ "/system/status": systemStatusResponse, "/scenarios": scenariosResponse });
    renderWithProviders(
      <Routes>
        <Route path="/new" element={<CreateInvestigationPage />} />
      </Routes>,
      ["/new"],
    );
    expect(await screen.findByText("权限不足")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "提交调查" })).not.toBeInTheDocument();
  });
});
