import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: './e2e', timeout: 45000, workers: 1, reporter: 'list', use: { baseURL: process.env.WEB_URL || 'http://localhost:3000', channel: 'chrome', headless: true, trace: 'retain-on-failure', screenshot: 'only-on-failure' } });
