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

    await page.goto('/dashboard/accounts/new');

    await expect(page.getByRole('heading', { name: 'Identity', exact: true })).toBeVisible();
    await page.getByPlaceholder('Hon. Shri/Smt…').fill('Shri Jagdish Shettar');
    await page.getByPlaceholder('e.g. Karnataka').fill('Karnataka');
    await page.getByRole('button', { name: /Continue to Seat & Access/ }).click();

    await expect(page.getByRole('heading', { name: 'Seat & Access', exact: true })).toBeVisible();
    await page.getByLabel('Parliamentary constituency').selectOption('Bangalore North');
    await page.getByLabel('Username').fill('j_shettar');
    await page.getByLabel('Temporary password').fill('ValidPass1!');
    await page.getByRole('button', { name: /Continue to Configure/ }).click();

    await expect(page.getByRole('heading', { name: 'Configure', exact: true })).toBeVisible();
    await page.getByRole('button', { name: /Continue to Review & Create/ }).click();

    await expect(page.getByRole('heading', { name: 'Review & Create', exact: true })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Identity' }).getByText('Shri Jagdish Shettar', { exact: true })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Seat & Access' }).getByText('Bangalore North', { exact: true })).toBeVisible();

    const createRequestPromise = page.waitForRequest((request) =>
        request.url() === 'http://127.0.0.1:4011/api/admin/mps' && request.method() === 'POST'
    );
    await page.getByRole('button', { name: 'Create account and continue setup' }).click();
    const createRequest = await createRequestPromise;

    expect(createRequest.postDataJSON()).toMatchObject({
        name: 'Shri Jagdish Shettar',
        username: 'j_shettar',
        constituency: 'Bangalore North',
        state: 'Karnataka',
        account_stage: 'elected',
        seat_type: 'mp',
    });

    await expect(page.getByText(/Created Shri Jagdish Shettar/i)).toBeVisible();
    await expect(page).toHaveURL(/\/dashboard\/mps\/7\/setup$/);
});
