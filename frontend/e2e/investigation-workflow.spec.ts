import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, username: string, password: string, verifyStubLabel = false) {
  await expect(page.getByLabel("登录表单")).toBeVisible();
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page.getByText(new RegExp(`· ${username}$`))).toBeVisible();
  if (verifyStubLabel) {
    await expect(page.getByTestId("synthetic-backend-banner")).toContainText("不代表真实 WARDEN、模型运行或实验结果");
  }
}

async function logout(page: Page) {
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page.getByLabel("登录表单")).toBeVisible();
}

async function createProjectAndLink(page: Page, name: string, requestId: string) {
  await page.getByRole("link", { name: "项目管理" }).click();
  await page.getByRole("button", { name: "新建项目" }).click();
  await page.getByPlaceholder("项目名称（唯一）").fill(name);
  await page.getByRole("button", { name: "创建", exact: true }).click();

  const project = page.locator("section").filter({
    has: page.getByRole("heading", { name }),
  });
  await expect(project).toBeVisible();
  await project.getByRole("button", { name: "管理" }).click();
  await project.getByPlaceholder("AgentGuard request_id").fill(requestId);
  await project.getByRole("button", { name: "关联" }).click();
  await expect(project.getByRole("link", { name: requestId })).toBeVisible();
  return project;
}

async function apiCall(
  page: Page,
  path: string,
  options: { method?: string; body?: Record<string, unknown>; csrf?: boolean } = {},
) {
  return page.evaluate(async ({ path, method, body, csrf }) => {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (body) headers["Content-Type"] = "application/json";
    if (csrf) {
      const token = document.cookie.match(/(?:^|;\s*)qwb_csrf=([^;]+)/)?.[1];
      headers["X-CSRF-Token"] = token ? decodeURIComponent(token) : "";
    }
    const response = await fetch(path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    return {
      status: response.status,
      body: await response.json().catch(() => null),
    };
  }, { path, ...options });
}

test("login, project investigation, verified loop, evidence, evaluation, exports, and isolation", async ({ page }) => {
  await page.goto("/");
  await login(page, "user-a", "user-a-e2e-password", true);

  const projectA = await createProjectAndLink(page, "J7 User A Project", "inv-stub-0001");
  await projectA.getByPlaceholder("用户名").fill("user-b");
  await projectA.locator("select").selectOption("viewer");
  await projectA.getByRole("button", { name: "添加" }).click();
  const userBMembership = projectA.locator("li").filter({ hasText: "user-b" });
  await expect(userBMembership).toBeVisible();
  await userBMembership.getByRole("button", { name: "移除" }).click();
  await expect(userBMembership).toHaveCount(0);

  await projectA.getByRole("link", { name: "inv-stub-0001" }).click();
  await expect(page.getByRole("heading", { name: "调查工作区" })).toBeVisible();
  await expect(page.getByText("loop-stub-001")).toBeVisible();
  await expect(page.getByText("归属已由 AgentGuard Live 列表验证")).toBeVisible();
  await page.getByRole("link", { name: /查看多轮记录/ }).click();
  await expect(page.getByRole("heading", { name: "Loop 概况" })).toBeVisible();
  await expect(page.getByText("loop-stub-001")).toBeVisible();
  await expect(page.getByRole("heading", { name: "证据变化" })).toBeVisible();
  await expect(page.getByText("ev-report-001")).toBeVisible();

  const csrfRejected = await apiCall(page, "/api/projects", {
    method: "POST",
    body: { name: "must-not-exist-without-csrf", description: null },
  });
  expect(csrfRejected.status).toBe(403);

  const createDenied = await apiCall(page, "/api/investigations/inv-stub-0001/loops", {
    method: "POST",
    csrf: true,
    body: {
      submission_id: "00000000-0000-4000-8000-000000000001",
      strategy: "risk_score",
      max_actions: 8,
      max_seconds: 30,
      max_model_calls: 1,
      no_new_evidence_rounds: 1,
      data_partition: "test",
    },
  });
  expect(createDenied.status).toBe(403);
  expect(createDenied.body).toMatchObject({ detail: { error: "PERMISSION_DENIED" } });

  const unknownLoop = await apiCall(page, "/api/investigation-loops/loop-unknown-j7");
  expect(unknownLoop.status).toBe(404);

  await page.goto("/multi-round-report?request_id=inv-stub-0001&loop_id=loop-stub-001");
  await expect(page.getByTestId("live-investigation-report")).toBeVisible();
  await expect(page.getByText(/确定性合同 Stub/)).toBeVisible();
  const [jsonDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "下载 JSON" }).click(),
  ]);
  expect(jsonDownload.suggestedFilename()).toMatch(/\.json$/);
  const jsonPath = await jsonDownload.path();
  expect(jsonPath).not.toBeNull();
  const exportedJson = await import("node:fs/promises").then(({ readFile }) => readFile(jsonPath!, "utf8"));
  expect(exportedJson).toContain("确定性合同 Stub");

  const [pdfDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "导出 PDF" }).click(),
  ]);
  expect(pdfDownload.suggestedFilename()).toMatch(/\.pdf$/);
  const pdfPath = await pdfDownload.path();
  expect(pdfPath).not.toBeNull();
  const pdfBytes = await import("node:fs/promises").then(({ readFile }) => readFile(pdfPath!));
  expect(pdfBytes.subarray(0, 5).toString("ascii")).toBe("%PDF-");

  await logout(page);
  await login(page, "alice", "alice-e2e-password");
  await page.goto("/strategy-comparison");
  await expect(page.getByRole("heading", { name: "策略评价" })).toBeVisible();
  await expect(page.getByTestId("strategy-evaluation-detail")).toContainText("Contract fixture only; no live evaluation was run.");

  await logout(page);
  await login(page, "user-b", "user-b-e2e-password");
  const removedMemberReport = await apiCall(
    page,
    "/api/reports/investigations/inv-stub-0001/loops/loop-stub-001/export.json",
  );
  expect(removedMemberReport.status).toBe(404);

  const projectB = await createProjectAndLink(page, "J7 User B Project", "inv-stub-graph-0002");
  await projectB.getByRole("link", { name: "inv-stub-graph-0002" }).click();
  await expect(page.getByText("loop-stub-002")).toBeVisible();
  await page.getByRole("link", { name: /查看多轮记录/ }).click();
  await expect(page.getByRole("heading", { name: "Loop 概况" })).toBeVisible();
  await expect(page.getByText("loop-stub-002")).toBeVisible();

  await logout(page);
  await login(page, "user-a", "user-a-e2e-password");
  const crossProjectLoop = await apiCall(page, "/api/investigation-loops/loop-stub-002");
  expect(crossProjectLoop.status).toBe(404);
  const crossProjectJson = await apiCall(
    page,
    "/api/reports/investigations/inv-stub-graph-0002/loops/loop-stub-002/export.json",
  );
  expect(crossProjectJson.status).toBe(404);
  const crossProjectPdf = await apiCall(
    page,
    "/api/reports/investigations/inv-stub-graph-0002/loops/loop-stub-002/export.pdf",
  );
  expect(crossProjectPdf.status).toBe(404);
  await logout(page);
});
