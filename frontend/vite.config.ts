import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

export default defineConfig(({ mode }) => {
  // 後端位址：環境變數優先（docker compose 用），其次 frontend/.env.local，最後才是預設值。
  // 本機 8000 常被其他專案佔用，所以個人設定放 .env.local（不進版控）。
  const env = loadEnv(mode, process.cwd(), '')
  const backendUrl = process.env.BACKEND_URL ?? env.BACKEND_URL ?? 'http://localhost:8000'
  return {
    plugins: [react()],
    server: {
      host: true,
      proxy: { '/api': backendUrl },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test-setup.ts'],
      exclude: ['e2e/**', 'node_modules/**'], // e2e 由 Playwright 執行
    },
  }
})
