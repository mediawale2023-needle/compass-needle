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
        if (url.pathname === '/api/auth/me') return route.fulfill({ json: { username: 'mp_arun', role: 'mp', constituency: 'Bangalore North' } });

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

async function mockMpBriefcaseWorkflowApi(page, withSibling = false) {
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
        if (url.pathname === '/api/auth/me') return ok({ username: 'mp_arun', role: 'mp', constituency: 'Bangalore North' });

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
        if (url.pathname === '/api/cases/2592' && req.method() === 'GET') return ok({ ...state.case, ...(withSibling ? { thread_cases: [{ ...state.case, id: 2593, case_ref: 'NDL-2026-02593', raw_message: 'Streetlight is not working', notes_for_staff: '', response_to_citizen: '' }, state.case] } : {}) });
        if (url.pathname === '/api/cases/2592/status' && req.method() === 'PATCH') {
            state.case.status = JSON.parse(req.postData()).status;
            return ok({ success: true });
        }

        if (url.pathname === '/api/cases/2592' && req.method() === 'PATCH') {
            const payload = JSON.parse(req.postData() || '{}');
            Object.assign(state.case, payload, { updated_at: '2026-05-08T02:09:00Z' });
            state.activities.unshift({ id: 1, username: 'mp_arun', action: 'case_updated', created_at: '2026-05-08T02:09:00Z' });
            return ok({ success: true });
        }
        if (url.pathname === '/api/cases/2592/notify/send' && req.method() === 'POST') {
            const payload = JSON.parse(req.postData() || '{}');
            state.case.response_to_citizen = payload.message || payload.response_to_citizen || state.case.response_to_citizen;
            state.activities.unshift({ id: 2, username: 'mp_arun', action: 'citizen_notified', new_value: 'whatsapp_sent', created_at: '2026-05-08T02:11:00Z' });
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
    await expect(page.getByText('Bureaucratic / Administrative').first()).toBeVisible();
    await expect(page.getByRole('button', { name: /Open case/ }).first()).toBeVisible();
});

test('Briefcase supports assign note notify and resolved workflow', async ({ page }) => {
    await seedMpSession(page);
    await mockMpBriefcaseWorkflowApi(page);

    await page.goto('/dashboard/sansadx');

    await expect(page.getByRole('heading', { name: 'Briefcase' })).toBeVisible();
    await page.getByText('No water supply in Whitefield for 3 days', { exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Case NDL-2026-02592', exact: true, level: 1 })).toBeVisible();
    await page.getByLabel('ASSIGNED TO', { exact: true }).selectOption('pr_meera');
    await page.getByRole('button', { name: 'INTERNAL NOTES' }).click();
    await page.getByRole('textbox', { name: 'Internal notes — office staff only' }).fill('Called ward engineer and assigned to PR.');
    await page.getByRole('button', { name: 'Save notes', exact: true }).click();
    await expect(page.getByText('Notes saved', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Reply to citizen', exact: true }).click();
    await page.getByRole('textbox', { name: 'Message', exact: true }).fill('Your water supply complaint is being reviewed and we will keep you updated.');
    await page.getByRole('button', { name: 'Send WhatsApp reply' }).click();
    await expect(page.getByText('WhatsApp reply sent — complaint status unchanged')).toBeVisible();
    await expect(page.getByLabel('NEEDLE STATUS', { exact: true })).toHaveValue('new');
    await expect(page.getByRole('heading', { name: 'Case NDL-2026-02592', exact: true, level: 1 })).toBeVisible();
    await page.getByRole('button', { name: 'Resolve complaint', exact: true }).click();
    await page.getByRole('button', { name: 'Confirm resolution' }).click();
    await expect(page.getByLabel('NEEDLE STATUS', { exact: true })).toHaveValue('resolved');
    await expect(page.getByRole('button', { name: 'Reply to citizen', exact: true })).toBeVisible();
});

for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    test(`Case Detail layout ${viewport.width}`, async ({ page }) => {
        await page.setViewportSize(viewport);
        await seedMpSession(page);
        await mockMpBriefcaseWorkflowApi(page);
        await page.goto('/dashboard/sansadx');
        await page.getByText('No water supply in Whitefield for 3 days', { exact: true }).click();
        await expect(page.getByRole('tabpanel')).toBeVisible();
        await expect(page.getByRole('tab')).toHaveAttribute('aria-selected', 'true');
        await page.screenshot({ path: `test-results/case-detail-${viewport.width}.png`, fullPage: false, animations: 'disabled' });
        await expect(page.getByRole('region', { name: 'AI UNDERSTANDING' })).toBeHidden();
        await page.getByRole('button', { name: 'AI UNDERSTANDING' }).click();
        await expect(page.getByRole('region', { name: 'AI UNDERSTANDING' })).toBeVisible();
        const workspace = page.locator('.case-detail-workspace');
        expect(await workspace.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
        await page.getByRole('button', { name: 'Reply to citizen', exact: true }).click();
        await expect(page.getByLabel('Message', { exact: true })).toBeFocused();
        await page.screenshot({ path: `test-results/case-reply-${viewport.width}.png`, fullPage: false, animations: 'disabled' });
    });
}

test('Complaint switching keeps drafts separate and a failed reply preserves text', async ({ page }) => {
    await seedMpSession(page);
    await mockMpBriefcaseWorkflowApi(page, true);
    await page.goto('/dashboard/sansadx');
    await page.getByText('No water supply in Whitefield for 3 days', { exact: true }).click();
    await expect(page.getByRole('tab')).toHaveCount(2);
    await page.getByRole('button', { name: 'Reply to citizen', exact: true }).click();
    await page.getByLabel('Message', { exact: true }).fill('Water complaint draft');
    await page.getByRole('button', { name: 'Keep draft & close' }).click();
    await page.getByRole('tab', { name: /COMPLAINT 2/ }).click();
    await page.getByRole('button', { name: 'Reply to citizen', exact: true }).click();
    await expect(page.getByLabel('Message', { exact: true })).toHaveValue('');
    await page.getByLabel('Message', { exact: true }).fill('Streetlight complaint draft');
    await page.route('**/api/cases/2593/notify/send', route => route.fulfill({ status: 500, json: { detail: 'Unable to send right now.' } }));
    await page.getByRole('button', { name: 'Send WhatsApp reply' }).click();
    await expect(page.getByRole('alert')).toContainText('Unable to send');
    await expect(page.getByLabel('Message', { exact: true })).toHaveValue('Streetlight complaint draft');
    await page.getByRole('button', { name: 'Keep draft & close' }).click();
    await page.getByRole('tab', { name: /COMPLAINT 1/ }).click();
    await page.getByRole('button', { name: 'Reply to citizen', exact: true }).click();
    await expect(page.getByLabel('Message', { exact: true })).toHaveValue('Water complaint draft');
});
