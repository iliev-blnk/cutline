import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:4173/cutline/",
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined },
  },
  webServer: { command: "pnpm build && pnpm preview", url: "http://localhost:4173/cutline/", timeout: 120_000, reuseExistingServer: true },
});
