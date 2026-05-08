const { test, expect } = require('@playwright/test');

async function seedMpSession(page) {
    await page.addInitScript(() => {
        sessionStorage.setItem('needle_token', 'mp-token-123');
        sessionStorage.setItem('needle_user', JSON.stringify({
            username: 'mp_arun',
            display_name: 'Arun Kumar',
            role: 'mp',
            constituency: 'Bangalore North',
            house: 'Lok Sabha',
        }));
    });
}

async function mockMpBriefcaseApi(page) {
    await page.route('http://127.0.0.1:4010/**', async (route) => {
        const url = new URL(route.request().url());

        if (url.pathname === '/api/dashboard/summary') {
            return route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ status_breakdown: { new: 1 }, category_breakdown: {}, red_zones: [], critical_count: 0 }),
            });
        }
        if (url.pathname === '/api/letterbox') {
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total: 0, items: [] }) });
        }
        if (url.pathname === '/api/announcements/active') {
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ announcements: [] }) });
        }
        if (url.pathname === '/api/staff') {
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ staff: [] }) });
        }
        if (url.pathname === '/api/cases') {
            return route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    cases: [
                        {
                            id: 2592,
                            user_phone: '919650787758',
                            category: 'Bureaucratic / Administrative',
                            status: 'new',
                            raw_message: 'Talati paise magat aahe. Majhi madad kara',
                            location: 'Unknown',
                            created_at: '2026-05-08T02:08:00Z',
                            case_metadata: { matched_value: '', assembly_constituency: '' },
                        },
                    ],
                    total: 1,
                    page: 1,
                    pages: 1,
                }),
            });
        }

        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
    });
}

test('Briefcase loads and shows case data for an authenticated MP', async ({ page }) => {
    await seedMpSession(page);
    await mockMpBriefcaseApi(page);

    await page.goto('/dashboard/sansadx');

    await expect(page.getByRole('heading', { name: 'Briefcase' })).toBeVisible();
    await expect(page.getByText('Bureaucratic / Administrative')).toBeVisible();
    await expect(page.getByText('919650787758')).toBeVisible();
});
