import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SettingsPage } from "../../pages/SettingsPage";
import { useAuthStore } from "../../stores/auth-store";

const settingsResponse = {
  meta: { data_mode: "unavailable" },
  auth_enabled: true,
  current_user: { username: "viewer", role: "viewer", display_name: "只读用户" },
  roles: [
    { name: "Viewer", description: "只读调查和报告。" },
    { name: "Analyst", description: "创建允许的调查、查看证据。" },
    { name: "Operator", description: "管理经授权的操作请求（不等价于 AgentGuard 高权限操作员）。" },
    { name: "Admin", description: "管理系统设置和用户。" },
  ],
};

function renderWithProviders(ui: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useAuthStore.getState().setSession({ role: "viewer", username: "viewer", authEnabled: true });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(settingsResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });

  it("shows roles, auth mode and current user", async () => {
    renderWithProviders(<SettingsPage />);
    expect(await screen.findByText("角色与权限")).toBeInTheDocument();
    expect(screen.getByText("AUTH_ENABLED")).toBeInTheDocument();
    expect(screen.getByText(/只读用户（viewer）/)).toBeInTheDocument();
    expect(screen.getByText("Operator")).toBeInTheDocument();
  });

  it("states operator is not an AgentGuard high-privilege operator", async () => {
    renderWithProviders(<SettingsPage />);
    expect(
      await screen.findByText(/应用层角色不授予 AgentGuard 高权限操作员身份/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Token 仅存在于服务端/)).toBeInTheDocument();
  });
});
