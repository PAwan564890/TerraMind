import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests/e2e",
  workers: 1,
  projects: [
    {
      name: "baseline",
      testMatch: "**/workflow.spec.ts",
      use: { baseURL: process.env.REACT_TEST_URL || "http://127.0.0.1:5173" },
    },
    {
      name: "expanded",
      testMatch: "**/foundations.spec.ts",
      use: {
        baseURL: process.env.REACT_EXPANDED_TEST_URL || "http://127.0.0.1:5174",
      },
    },
  ],
  use: {
    baseURL: process.env.REACT_TEST_URL || "http://127.0.0.1:5173",
    launchOptions: {
      executablePath: process.env.CHROMIUM_PATH,
      args: ["--no-sandbox"],
    },
    screenshot: "only-on-failure",
  },
  reporter: "list",
});
