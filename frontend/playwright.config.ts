import { defineConfig, devices } from "@playwright/test";

const chromiumPath = process.env.PW_CHROMIUM_PATH;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  outputDir: "test-results",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "off",
    screenshot: "only-on-failure",
    launchOptions: chromiumPath ? { executablePath: chromiumPath } : {},
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
