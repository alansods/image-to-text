import { defineConfig, devices } from "@playwright/test";

// E2E: sobe o Next em modo dev e testa em desktop e celular (spec site-interface).
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  // Uma conversão por vez: o servidor limita 3 ativas por endereço.
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL: "http://localhost:3000",
    locale: "pt-BR",
    trace: "on-first-retry",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "celular", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
  },
});
