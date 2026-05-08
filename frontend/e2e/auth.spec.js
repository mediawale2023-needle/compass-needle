const { test, expect } = require('@playwright/test');

async function mockMpApi(page) {
    await page.route('http://127.0.0.1:4010/**', async (route) => {
        const request = route.request();
        const url = new URL(request.url());

        if (url.pathname === '/health') {
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) });
        }
        if (url.pathname === '/api/auth/login' && request.method() === 'POST') {
            return route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    token: 'mp-token-123',
                    user: {
                        username: 'mp_arun',
                        display_name: 'Arun Kumar',
                        role: 'mp',
                        constituency: 'Bangalore North',
                        house: 'Lok Sabha',
                    },
                }),
            });
        }
        if (url.pathname === '/api/dashboard/summary') {
            return route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    category_breakdown: { Water: 2 },
                    status_breakdown: { new: 1, resolved: 2 },
                    red_zones: [{ area: 'Whitefield', cnt: 1 }],
                    critical_count: 1,
                }),
            });
        }
        if (url.pathname === '/api/activity/report-card') {
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
        }
        if (url.pathname === '/api/news') {
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ articles: [] }) });
        }
        if (url.pathname === '/api/cases') {
            return route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    cases: [
                        {
                            id: 101,
                            user_phone: '919111111111',
                            category: 'Water',
                            status: 'new',
                            raw_message: 'Pipeline burst in Whitefield',
                            created_at: '2026-05-07T09:00:00Z',
                        },
                    ],
                    total: 1,
                    page: 1,
                    pages: 1,
                }),
            });
        }
        if (url.pathname === '/api/letterbox') {
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total: 0, items: [] }) });
        }
        if (url.pathname === '/api/announcements/active') {
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ announcements: [] }) });
        }

        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
    });
}

test('MP can sign in and reach the dashboard', async ({ page }) => {
    await mockMpApi(page);

    await page.goto('/');
    await page.getByPlaceholder('Enter your username').fill('mp_arun');
    await page.getByPlaceholder('Enter your password').fill('ValidPass1!');
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByText('Total Cases')).toBeVisible();
    await expect(page.getByText('Review Now')).toBeVisible();

    const token = await page.evaluate(() => sessionStorage.getItem('needle_token'));
    await expect(token).toBe('mp-token-123');
});
