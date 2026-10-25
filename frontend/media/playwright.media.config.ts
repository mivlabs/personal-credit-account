import { defineConfig } from '@playwright/test';

// Съёмка медиа для README: `npm run media`. Отдельный конфиг, в `npm run test:e2e` и CI не попадает.
// Нужны запущенные API (localhost:8000) и dev-сервер (`npm run dev`, порт 5173) на чистой БД.
export default defineConfig({
  testDir: './',
  testMatch: 'capture.spec.ts',
  timeout: 180000,
  workers: 1,
  expect: { timeout: 20000 },
  reporter: 'list',
  outputDir: '../test-results/media',
  use: {
    baseURL: process.env.MEDIA_URL || 'http://localhost:5173',
    channel: 'chrome',
    headless: true,
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 1,
  },
});
