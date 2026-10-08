import { defineConfig, devices } from '@playwright/test'

const BACKEND_PORT = 8041
const FRONTEND_PORT = 5199
const CI = Boolean(process.env.CI)

/**
 * E2E：真的瀏覽器 → 真的前端 → 真的 FastAPI（SSE、速率限制、錯誤處理），
 * 只有模型、檢索與條文是假的（backend/tests/e2e_server.py），所以不需要任何金鑰。
 *
 *   pnpm e2e            跑全部
 *   pnpm e2e --ui       互動模式
 */
export default defineConfig({
  testDir: 'e2e',
  workers: 1, // 共用同一個假後端，逐一執行最單純
  retries: CI ? 1 : 0,
  reporter: CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: 'retain-on-failure',
    locale: 'zh-TW',
  },
  projects: [
    {
      name: 'desktop',
      testIgnore: /mobile\.spec/,
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'mobile',
      testMatch: /mobile\.spec/,
      use: { ...devices['Pixel 7'], viewport: { width: 390, height: 844 } },
    },
  ],
  webServer: [
    {
      command: `uv run python -m tests.e2e_server --port ${BACKEND_PORT}`,
      cwd: '../backend',
      url: `http://localhost:${BACKEND_PORT}/api/health`,
      reuseExistingServer: !CI,
      timeout: 60_000,
    },
    {
      command: `pnpm exec vite --port ${FRONTEND_PORT} --strictPort`,
      env: { BACKEND_URL: `http://localhost:${BACKEND_PORT}` },
      url: `http://localhost:${FRONTEND_PORT}`,
      reuseExistingServer: !CI,
      timeout: 60_000,
    },
  ],
})
