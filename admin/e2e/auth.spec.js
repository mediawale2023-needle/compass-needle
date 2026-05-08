const { test, expect } = require('@playwright/test');

async function mockAdminApi(page) {
    await page.route('http://127.0.0.1:4011/**', async (route) => {
        const request = route.request();
        const url = new URL(request.url());

        if (url.pathname === '/health') {
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) });
        }
        if (url.pathname === '/api/admin/auth/login' && request.method() === 'POST') {
            return route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    token: 'admin-token-123',
                    user: {
                        username: 'sysadmin',
                        display_name: 'System Admin',
                        role: 'sysadmin',
                    },
                }),
            });
        }
        if (url.pathname === '/api/admin/alerts') {
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ alerts: [] }) });
        }
        if (url.pathname === '/api/admin/system-health') {
            return route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    last_checked: '2026-05-08T09:00:00Z',
                    whatsapp: { status: 'green', last_webhook: '2026-05-08T08:45:00Z' },
                    openai: { status: 'green', configured: true },
                    gemini: { status: 'green', configured: true },
                }),
            });
        }
        if (url.pathname === '/api/admin/stats') {
            return route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    total_mps: 2,
                    lok_sabha: 1,
                    rajya_sabha: 1,
                    total_profiles: 2,
                    total_cases: 14,
                }),
            });
        }
        if (url.pathname === '/api/admin/mps') {
            return route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    mps: [
                        {
                            tenant_id: 1,
                            display_name: 'Arun Kumar',
                            username: 'mp_arun',
                            house: 'Lok Sabha',
                            parliamentary_constituency: 'Bangalore North',
                            completeness: 82,
                        },
                    ],
                }),
            });
        }

        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
    });
}

test('Admin can sign in and reach the overview dashboard', async ({ page }) => {
    await mockAdminApi(page);

    await page.goto('/');
    await page.getByPlaceholder('Enter your username').fill('sysadmin');
    await page.getByPlaceholder('Enter your password').fill('AdminPass1!');
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByText('Members of Parliament')).toBeVisible();

    const token = await page.evaluate(() => sessionStorage.getItem('admin_token'));
    await expect(token).toBe('admin-token-123');
});
