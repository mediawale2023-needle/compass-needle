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

async function mockMpBriefcaseWorkflowApi(page) {
    const state = {
        case: {
            id: 2592,
            case_ref: 'NDL-2026-02592',
            user_phone: '919650787758',
            category: 'Infrastructure & Utilities',
            status: 'new',
            raw_message: 'No water supply in Whitefield for 3 days',
            location: 'Whitefield',
            assembly: 'Mahadevapura',
            created_at: '2026-05-08T02:08:00Z',
            updated_at: '2026-05-08T02:08:00Z',
            case_metadata: {
                matched_value: 'Whitefield',
                assembly_constituency: 'Mahadevapura',
                summary: 'Water outage in Whitefield',
            },
            notes_for_staff: '',
            response_to_citizen: '',
            assigned_to: '',
        },
        activities: [],
    };

    await page.route('http://127.0.0.1:4010/**', async (route) => {
        const req = route.request();
        const url = new URL(req.url());
        const ok = (body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

        if (url.pathname === '/api/dashboard/summary') {
            return ok({ status_breakdown: { new: state.case.status === 'new' ? 1 : 0 }, category_breakdown: {}, red_zones: [], critical_count: 0 });
        }
        if (url.pathname === '/api/letterbox') return ok({ total: 0, items: [] });
        if (url.pathname === '/api/announcements/active') return ok({ announcements: [] });
        if (url.pathname === '/api/staff') {
            return ok({ staff: [{ username: 'pr_meera', display_name: 'Meera PR', role: 'pr' }] });
        }
        if (url.pathname === '/api/cases') {
            return ok({ cases: [state.case], total: 1, page: 1, pages: 1 });
        }
        if (url.pathname === '/api/cases/2592/activity') return ok({ activities: state.activities });
        if (url.pathname === '/api/cases/2592/similar') return ok({ cases: [] });

        if (url.pathname === '/api/cases/2592' && req.method() === 'PATCH') {
            const payload = JSON.parse(req.postData() || '{}');
            Object.assign(state.case, payload, { updated_at: '2026-05-08T02:09:00Z' });
            state.activities.unshift({ id: 1, username: 'mp_arun', action: 'case_updated', created_at: '2026-05-08T02:09:00Z' });
            return ok({ success: true });
        }
        if (url.pathname === '/api/cases/2592/notify/send' && req.method() === 'POST') {
            const payload = JSON.parse(req.postData() || '{}');
            state.case.status = 'resolved';
            state.case.response_to_citizen = payload.message || payload.response_to_citizen || state.case.response_to_citizen;
            state.activities.unshift({ id: 2, username: 'mp_arun', action: 'citizen_notified', new_value: 'resolved', created_at: '2026-05-08T02:11:00Z' });
            return ok({ success: true, message: 'Notification sent to citizen via WhatsApp' });
        }

        return ok({});
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

test('Briefcase supports assign note notify and resolved workflow', async ({ page }) => {
    await seedMpSession(page);
    await mockMpBriefcaseWorkflowApi(page);

    await page.goto('/dashboard/sansadx');

    await expect(page.getByRole('heading', { name: 'Briefcase' })).toBeVisible();
    await page.getByText('No water supply in Whitefield').click();

    await expect(page.getByRole('heading', { name: 'Infrastructure & Utilities' })).toBeVisible();
    await page.locator('select').last().selectOption('pr_meera');
    await page.getByPlaceholder('Internal notes...').fill('Called ward engineer and assigned to PR.');
    await page.getByPlaceholder('Response message...').fill('Your water supply complaint is being reviewed and we will keep you updated.');
    await page.getByRole('button', { name: 'Save Notes' }).click();
    await expect(page.getByText('Notes saved successfully')).toBeVisible();
    await page.getByRole('button', { name: /Send Update via WhatsApp/ }).click();
    await page.getByPlaceholder('Type NDL-2026-02592 to confirm').fill('NDL-2026-02592');
    await page.getByRole('button', { name: 'Confirm & Send' }).click();
    await expect(page.getByText('WhatsApp update sent')).toBeVisible();

    await page.getByText('No water supply in Whitefield').click();
    await expect(page.getByText('Resolved · NDL-2026-02592')).toBeVisible();
    await expect(page.getByText('Resolution Message Sent to Citizen')).toBeVisible();
});
