const { defineConfig, devices } = require("@playwright/test");

const port = Number(process.env.GKGUARD_E2E_PORT || 8012);
const baseURL = `http://127.0.0.1:${port}`;

module.exports = defineConfig({
  testDir: "./tests/e2e",
  timeout: 35_000,
  expect: {
    timeout: 6_000,
  },
  fullyParallel: false,
  reporter: process.env.CI ? [["list"]] : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    actionTimeout: 8_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `python -m uvicorn app.main:app --host 127.0.0.1 --port ${port}`,
    cwd: "./backend",
    url: `${baseURL}/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: "desktop-1280",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      name: "compact-680",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 680, height: 640 },
      },
    },
    {
      name: "mobile-390",
      use: {
        ...devices["Pixel 5"],
        viewport: { width: 390, height: 720 },
      },
    },
  ],
});
