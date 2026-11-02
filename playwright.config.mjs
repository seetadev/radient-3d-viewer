import { defineConfig } from '@playwright/test';

const port = process.env.E2E_PORT || '8899';
export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 90_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${port}`,
    viewport: { width: 1000, height: 700 },
    launchOptions: { args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] },
  },
  webServer: {
    command: `${process.env.PYTHON || 'python'} run.py ${port}`,
    url: `http://localhost:${port}/main`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
