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

    await expect.poll(async () => page.evaluate(() => sessionStorage.getItem('admin_token'))).toBe('admin-token-123');

    const token = await page.evaluate(() => sessionStorage.getItem('admin_token'));
    await expect(token).toBe('admin-token-123');
});

test('Admin navigation remains available on a narrow viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => {
        sessionStorage.setItem('admin_token', 'admin-token-123');
        sessionStorage.setItem('admin_user', JSON.stringify({ username: 'sysadmin', display_name: 'System Admin', role: 'sysadmin' }));
    });
    await mockAdminApi(page);
    await page.goto('/dashboard');

    // Shell landmarks by role (the Phase 1 shell renamed its classes).
    const shell = page.getByRole('main');
    // The closed drawer is visibility:hidden (out of the a11y tree), so locate it by label.
    const sidebar = page.locator('aside[aria-label="Needle Admin"]');
    await expect(page.getByRole('button', { name: 'Open navigation' })).toBeVisible();
    await expect(sidebar).toHaveAttribute('data-open', 'false');
    await expect.poll(async () => page.evaluate(() => {
        const main = document.getElementById('main-content').parentElement;
        return {
            clientWidth: document.documentElement.clientWidth,
            scrollWidth: document.documentElement.scrollWidth,
            mainWidth: Math.round(main.getBoundingClientRect().width),
            mainLeft: Math.round(main.getBoundingClientRect().left),
        };
    })).toEqual({ clientWidth: 390, scrollWidth: 390, mainWidth: 390, mainLeft: 0 });

    await page.getByRole('button', { name: 'Open navigation' }).click();
    await expect(sidebar).toHaveAttribute('data-open', 'true');
    await expect(sidebar.getByRole('link', { name: 'Messaging', exact: true })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: 'People & Access', exact: true })).toBeVisible();

    await sidebar.getByRole('button', { name: 'Close navigation' }).click();
    await expect(sidebar).toHaveAttribute('data-open', 'false');
    await expect(shell).toBeVisible();
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
});

test('Case Explorer is the default workspace and Messaging has one local navigation', async ({ page }) => {
    await page.addInitScript(() => {
        sessionStorage.setItem('admin_token', 'admin-token-123');
        sessionStorage.setItem('admin_user', JSON.stringify({ username: 'sysadmin', display_name: 'System Admin', role: 'sysadmin' }));
    });
    await mockAdminApi(page);

    await page.goto('/dashboard/cases-intelligence/explorer');
    await expect(page.getByRole('heading', { name: 'Case Explorer', exact: true })).toBeVisible();
    // Phase 4: the explorer is primary; analytics and case health are a
    // compact view toggle (renamed from Case Explorer / Platform Health).
    const views = page.getByRole('group', { name: 'Case view' });
    await expect(views.getByRole('button', { name: 'Cases', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(views.getByRole('button', { name: 'Case health', exact: true })).toHaveAttribute('aria-pressed', 'false');
    await expect(page.getByRole('navigation', { name: 'Case Operations' }).getByRole('link', { name: 'Case Explorer' })).toHaveAttribute('aria-current', 'page');

    await page.goto('/dashboard/system/whatsapp');
    const messagingNav = page.getByRole('navigation', { name: 'Messaging operations' });
    await expect(messagingNav).toBeVisible();
    await expect(messagingNav.getByRole('link')).toHaveCount(5);
    await expect(page.getByRole('navigation', { name: 'Platform Operations' })).toHaveCount(0);
});
