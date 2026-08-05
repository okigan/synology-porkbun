import { defineConfig } from "@playwright/test";

const API_PORT = 8901;
const SITE_PORT = 8902;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  // Chrome allows only one browser process per extension profile, and the
  // backend keeps state between assertions, so run serially.
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 45_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${SITE_PORT}`,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      // Fresh database each run, and the offline search provider so verification
      // assertions never depend on the live web.
      command:
        "rm -f e2e.db && uv run uvicorn app.main:app " +
        `--host 127.0.0.1 --port ${API_PORT}`,
      cwd: "../backend",
      url: `http://127.0.0.1:${API_PORT}/healthz`,
      reuseExistingServer: false,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        CBL_DATABASE_URL: "sqlite+pysqlite:///./e2e.db",
        CBL_SEARCH_PROVIDER: "fixture",
        CBL_ANALYZER: "heuristic",
        CBL_SEED_ON_STARTUP: "true",
      },
    },
    {
      command: `python3 -m http.server ${SITE_PORT} --bind 127.0.0.1`,
      cwd: "./fixtures",
      url: `http://127.0.0.1:${SITE_PORT}/clean.html`,
      reuseExistingServer: false,
      stdout: "ignore",
    },
  ],
});

export { API_PORT, SITE_PORT };
