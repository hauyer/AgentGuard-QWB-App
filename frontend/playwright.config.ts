import { defineConfig, devices } from "@playwright/test";

// E2E smoke: the real frontend against the real BFF.
// Requires the backend to run (see README quickstart). Marked with @smoke.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  timeout: 60_000,
  retries: 0,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
