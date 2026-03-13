const { defineConfig } = require('@playwright/test');
const path = require('path');

module.exports = defineConfig({
  testDir: path.join(__dirname, 'tests'),
  timeout: 10 * 60 * 1000,
  expect: {
    timeout: 30 * 1000,
  },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8860',
    trace: 'on',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  outputDir: path.join(__dirname, 'test-results'),
  webServer: {
    command: 'python scripts/dashboard_service.py --host 127.0.0.1 --port 8860',
    url: 'http://127.0.0.1:8860/api/state',
    cwd: path.join(__dirname, '..'),
    reuseExistingServer: true,
    timeout: 60 * 1000,
  },
});
