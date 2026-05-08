const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
    testDir: './e2e',
    timeout: 30_000,
    use: {
        baseURL: 'http://127.0.0.1:3001',
        browserName: 'chromium',
        headless: true,
        trace: 'on-first-retry',
    },
    webServer: {
        command: 'npm run dev -- --hostname 127.0.0.1 --port 3001',
        port: 3001,
        reuseExistingServer: true,
        timeout: 120_000,
        env: {
            NEXT_PUBLIC_API_URL: 'http://127.0.0.1:4011',
        },
    },
});
