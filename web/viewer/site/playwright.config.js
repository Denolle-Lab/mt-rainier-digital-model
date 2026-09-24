import { defineConfig } from "@playwright/test";

const BASE = process.env.E2E_URL ?? "http://127.0.0.1:4176/rainier-seismic-atlas/";

export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: BASE,
    viewport: { width: 1440, height: 900 },
    channel: "chromium",
    launchOptions: { args: ["--use-gl=angle", "--enable-webgl", "--ignore-gpu-blocklist"] },
  },
  webServer: process.env.E2E_URL ? undefined : {
    command: "npm run build && npx vite preview --port 4176 --strictPort",
    url: BASE, reuseExistingServer: true, timeout: 180_000,
  },
});
