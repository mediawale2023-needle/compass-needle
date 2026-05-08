const { test, expect } = require('@playwright/test');

async function seedAdminSession(page) {
    await page.addInitScript(() => {
        sessionStorage.setItem('admin_token', 'admin-token-123');
        sessionStorage.setItem('admin_user', JSON.stringify({
            username: 'sysadmin',
            display_name: 'System Admin',
            role: 'sysadmin',
        }));
    });
}

async function mockAdminMpsApi(page) {
    await page.route('http://127.0.0.1:4011/**', async (route) => {
        const request = route.request();
        const url = new URL(request.url());

        if (url.pathname === '/api/admin/alerts') {
            return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ alerts: [] }) });
        }
        if (url.pathname === '/api/admin/constituencies') {
            return route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ constituencies: ['Bangalore North', 'Mumbai South'] }),
            });
        }
        if (url.pathname === '/api/admin/mps' && request.method() === 'POST') {
            return route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ tenant_id: 7 }),
            });
        }

        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
    });
}

test('Admin can create an MP from the new MP form', async ({ page }) => {
    await seedAdminSession(page);
    await mockAdminMpsApi(page);

    await page.goto('/dashboard/mps/new');
    await page.getByPlaceholder('Hon. Shri/Smt…').fill('Shri Jagdish Shettar');
    await page.getByPlaceholder('username').fill('j_shettar');
    await page.locator('input[type="password"]').first().fill('ValidPass1!');
    await page.getByPlaceholder('e.g. Karnataka').fill('Karnataka');
    await page.getByRole('button', { name: 'Create MP' }).click();

    await expect(page.getByText(/Created Shri Jagdish Shettar/i)).toBeVisible();
    await expect(page).toHaveURL(/\/dashboard\/mps\/7\/setup$/);
});
