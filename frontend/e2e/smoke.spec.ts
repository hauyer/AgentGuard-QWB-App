import { expect, test } from "@playwright/test";

// B0 smoke: the console boots, shows the global navigation and renders the
// real BFF status (live or explicit unavailable) - never a fabricated dashboard.
test("console boots and shows system status", async ({ page }) => {
  await page.goto("/system-overview");
  await expect(page.getByRole("heading", { name: "系统与诊断" })).toBeVisible();
  await expect(page.getByRole("navigation", {name:"主导航"})).toContainText("安全调查");
  // The status page must render one of the two honest outcomes.
  const live = page.getByText("LIVE", { exact: true });
  const synthetic = page.getByText("SYNTHETIC", { exact: true });
  const unavailable = page.getByText("UNAVAILABLE");
  await expect(live.or(synthetic).or(unavailable).first()).toBeVisible({ timeout: 15_000 });
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 1366, height: 768 },
    { width: 1024, height: 768 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
      .toBe(true);
    await page.screenshot({
      path: test.info().outputPath(`system-overview-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    });
  }

  await expect(page.getByRole("button", { name: "打开导航" })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("system-overview-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "打开导航" }).click();
  await expect(page.getByRole("navigation", {name:"主导航"})).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("mobile-navigation.png"), fullPage: true });
});
