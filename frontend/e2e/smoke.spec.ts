import { expect, test } from "@playwright/test";

// B0 smoke: the console boots, shows the global navigation and renders the
// real BFF status (live or explicit unavailable) - never a fabricated dashboard.
test("console boots and shows system status", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "系统总览" })).toBeVisible();
  await expect(page.getByRole("navigation")).toContainText("安全调查");
  // The status page must render one of the two honest outcomes.
  const live = page.getByText("LIVE");
  const unavailable = page.getByText("UNAVAILABLE");
  await expect(live.or(unavailable).first()).toBeVisible({ timeout: 15_000 });
});
