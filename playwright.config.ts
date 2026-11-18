import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  timeout: 60000,
  expect: { timeout: 20000 },
  use: { baseURL: "http://localhost:5173" },
  webServer: [
    {
      command:
        "uv run -m uvicorn backend.tests.e2e_app:create_app --factory --port 8000",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: false,
    },
    {
      command: "npx vite dashboard --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: false,
    },
  ],
});
