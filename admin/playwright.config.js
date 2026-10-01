const { defineConfig } = require('@playwright/test');

const adminPort = Number(process.env.ADMIN_E2E_PORT || 3001);
const adminBaseUrl = `http://127.0.0.1:${adminPort}`;
const mockApiUrl = process.env.ADMIN_E2E_API_URL || 'http://127.0.0.1:4011';

module.exports = defineConfig({
    testDir: './e2e',
    timeout: 30_000,
    use: {
        baseURL: adminBaseUrl,
        browserName: 'chromium',
        headless: true,
        trace: 'on-first-retry',
    },
    webServer: {
        command: `npm run dev -- --hostname 127.0.0.1 --port ${adminPort}`,
        port: adminPort,
        reuseExistingServer: true,
        timeout: 120_000,
        env: {
            NEXT_PUBLIC_API_URL: mockApiUrl,
        },
    },
});
