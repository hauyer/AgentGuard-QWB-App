import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "../../stores/auth-store";
import { ProjectsPage } from "../../pages/ProjectsPage";

const projectsPayload = {
  count: 1,
  total: 1,
  offset: 0,
  limit: 50,
  items: [
    {
      project_id: 7,
      name: "alpha",
      description: "first project",
      status: "active",
      created_by: "alice",
      investigation_count: 0,
    },
  ],
};

const detailPayload = {
  project: projectsPayload.items[0],
  membership_role: "admin",
};

const membersPayload = {
  count: 1,
  items: [{ username: "alice", role: "admin", added_by: "alice" }],
};

const investigationsPayload = { count: 0, items: [] };

function mockFetch(routes: Record<string, unknown>) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/projects/7/members") && (input as Request).method === "POST") {
      return new Response(JSON.stringify({ added: { username: "bob", role: "viewer" } }), {
        status: 201, headers: { "Content-Type": "application/json" } });
    }
    for (const [pattern, value] of Object.entries(routes)) {
      if (url.includes(pattern)) {
        return new Response(JSON.stringify(value), {
          status: 200, headers: { "Content-Type": "application/json" } });
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

describe("ProjectsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useAuthStore.setState({ role: "analyst", authEnabled: true, status: "ready", username: "alice" });
  });

  it("renders the project list and expands management panels", async () => {
    mockFetch({
      // order matters: longer prefixes must come first
      "/projects/7/members": membersPayload,
      "/projects/7/investigations": investigationsPayload,
      "/projects/7": detailPayload,
      "/projects": projectsPayload,
    });
    renderWithProviders(
      <Routes>
        <Route path="/" element={<ProjectsPage />} />
      </Routes>,
    );
    expect(await screen.findByText("alpha")).toBeInTheDocument();
    expect(screen.getByText("first project")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "管理" }));
    expect(await screen.findByText("调查引用")).toBeInTheDocument();
    expect(await screen.findByText("成员")).toBeInTheDocument();
    expect(screen.getByText("alice")).toBeInTheDocument();
  });

  it("hides the create button for viewer", async () => {
    useAuthStore.setState({ role: "viewer", authEnabled: true, status: "ready", username: "carol" });
    mockFetch({ "/projects": { count: 0, total: 0, offset: 0, limit: 50, items: [] } });
    renderWithProviders(
      <Routes>
        <Route path="/" element={<ProjectsPage />} />
      </Routes>,
    );
    expect(await screen.findByText(/您尚未加入任何项目/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "新建项目" })).not.toBeInTheDocument();
  });
});
