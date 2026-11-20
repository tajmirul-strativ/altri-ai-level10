import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against a running stack (`docker compose up`, or `pnpm dev` + the API).
 * Point E2E_BASE_URL elsewhere if needed. A trace is kept for every failed test
 * (open with `pnpm exec playwright show-trace <file>`).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  outputDir: "test-results",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
