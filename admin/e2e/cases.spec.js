const { test, expect } = require('@playwright/test');

const CASES = [
    {
        id: 1042, tenant_id: 2, mp: 'Avichal Dubey', constituency: 'Udaipur', phone: '+919400000218', category: 'Water Supply',
        status: 'in_progress', location: 'Kheda', assembly: 'Girwa', message: 'No tap water in Kheda since the 30th',
        created: '2026-09-30 18:47', created_at: '2026-09-30T18:47:00', critical: true, priority: 'critical',
        assigned_to: 'kavya', case_ref: 'UDR-1042', is_deleted: false, needs_geography_review: false,
    },
    {
        id: 1041, tenant_id: 3, mp: 'Priya Rao', constituency: 'Belagavi', phone: '+919800000101', category: 'Roads',
        status: 'new', location: '-', assembly: '-', message: 'Road near the school is broken',
        created: '2026-10-05 09:12', created_at: '2026-10-05T09:12:00', critical: false, priority: 'standard',
        assigned_to: null, case_ref: null, is_deleted: false, needs_geography_review: true,
    },
];

const DETAIL = {
    1042: {
        id: 1042, tenant_id: 2, mp_name: 'Avichal Dubey', mp_constituency: 'Udaipur', phone: '+919400000218',
        category: 'Water Supply', status: 'in_progress', critical: true, location: 'Kheda', assembly: 'Girwa', confidence: 'high',
        raw_message: 'हमारे गाँव खेड़ा में 30 तारीख से नल में पानी नहीं आ रहा।', response_to_citizen: '', notes_for_staff: 'Called the JE',
        case_ref: 'UDR-1042', priority: 'critical', assigned_to: 'kavya', is_deleted: false, problem_domain: 'Water Supply', problem_subdomain: null,
        timestamps: { created_at: '2026-09-30T18:47:00', updated_at: null, status_changed_at: '2026-10-01T11:02:00', resolved_at: null },
        government: { status: 'submitted', department: 'PHED', reference_number: 'PHED/UDR/412', status_updated_at: '2026-10-04T16:20:00', last_forwarded_to_citizen_at: null, portal: { name: 'Rajasthan Sampark', state: 'Rajasthan', type: 'state_branded' } },
        analysis: { summary: 'No tap water in Kheda since the 30th.', ai_category: 'Water Supply', ai_subcategory: 'Piped supply', ai_confidence: 0.82, category_decided_by: 'ai', needs_review: false, classification_mode: 'shadow', language: 'hindi', english_translation: 'No tap water in Kheda since the 30th.', department_mentioned: null, scheme_mentioned: null, geography: { confidence: 'high', source: 'gazetteer', needs_review: false, review_reason: null } },
        activity: [
            { username: 'system', action: 'status_change', old_value: 'new', new_value: 'in_progress', details: null, created_at: '2026-10-01T11:02:00' },
            { username: 'kavya', action: 'govt_submitted', old_value: null, new_value: 'PHED/UDR/412', details: null, created_at: '2026-10-04T16:20:00' },
        ],
        messages: { inbound: [{ id: 1, status: 'processed', message_type: 'text', created_at: '2026-09-30T18:47:00', processed_at: '2026-09-30T18:47:05' }], outbound: [{ id: 9, status: 'sent', body: 'We have registered your complaint.', template_key: 'ack', last_error: null, created_at: '2026-09-30T18:47:10', sent_at: '2026-09-30T18:47:11' }] },
    },
    1041: {
        id: 1041, tenant_id: 3, mp_name: 'Priya Rao', mp_constituency: 'Belagavi', phone: '+919800000101', category: 'Roads', status: 'new',
        critical: false, location: '-', assembly: '-', confidence: '-', raw_message: 'Road near the school is broken', response_to_citizen: '', notes_for_staff: '',
        case_ref: null, priority: 'standard', assigned_to: null, is_deleted: false, problem_domain: null, problem_subdomain: null,
        timestamps: { created_at: '2026-10-05T09:12:00', updated_at: null, status_changed_at: null, resolved_at: null },
        government: { status: 'not_forwarded', department: null, reference_number: null, status_updated_at: null, last_forwarded_to_citizen_at: null, portal: null },
        analysis: { summary: null, ai_category: null, ai_subcategory: null, ai_confidence: null, category_decided_by: null, needs_review: false, classification_mode: null, language: null, english_translation: null, department_mentioned: null, scheme_mentioned: null, geography: { confidence: null, source: null, needs_review: true, review_reason: null } },
        activity: [],
        messages: { inbound: [], outbound: [] },
    },
};

async function mockCasesApi(page, requests = []) {
    await page.addInitScript(() => {
        sessionStorage.setItem('admin_token', 'admin-token-123');
        sessionStorage.setItem('admin_user', JSON.stringify({ username: 'sysadmin', display_name: 'System Admin', role: 'sysadmin' }));
    });
    await page.route('http://127.0.0.1:4011/**', async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        requests.push(`${request.method()} ${url.pathname}${url.search}`);
        const json = (body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
        if (url.pathname === '/api/admin/cases/explorer') {
            let cases = CASES;
            if (url.searchParams.get('mp_id')) cases = cases.filter((c) => String(c.tenant_id) === url.searchParams.get('mp_id'));
            if (url.searchParams.get('priority')) cases = cases.filter((c) => c.priority === url.searchParams.get('priority'));
            return json({
                total: cases.length,
                cases,
                filter_options: { categories: ['Roads', 'Water Supply'], statuses: ['in_progress', 'new'], mps: [{ id: 2, name: 'Avichal Dubey', constituency: 'Udaipur' }, { id: 3, name: 'Priya Rao', constituency: 'Belagavi' }], priorities: ['critical', 'high', 'standard', 'low'] },
            });
        }
        const match = url.pathname.match(/^\/api\/admin\/cases\/(\d+)$/);
        if (match) return json(DETAIL[match[1]]);
        if (url.pathname === '/api/admin/alerts') return json({ alerts: [] });
        return json({});
    });
}

test('desktop explorer opens the investigation beside the list, read-only', async ({ page }) => {
    const requests = [];
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockCasesApi(page, requests);
    await page.goto('/dashboard/cases-intelligence/explorer');

    const list = page.getByRole('list', { name: 'Cases' });
    await expect(list.getByRole('button')).toHaveCount(2);
    // First case auto-opens on desktop and is marked selected.
    const first = list.getByRole('button').first();
    await expect(first).toHaveAttribute('aria-current', 'true');
    const detail = page.getByRole('article');
    await expect(detail.getByRole('heading', { name: 'Water Supply' })).toBeVisible();
    await expect(detail.getByText('AI-derived · not a staff decision')).toBeVisible();
    await expect(detail.getByRole('tab')).toHaveText(['Overview', 'Timeline2', 'Government', 'Notes1', 'Messages2']);
    await expect(detail.getByRole('link', { name: 'Open in MP workspace →' })).toHaveAttribute('href', '/dashboard/mps/2#support');
    for (const name of [/update status/i, /reassign/i, /escalate/i, /add note/i, /accept category/i]) {
        await expect(page.getByRole('button', { name })).toHaveCount(0);
    }
    await expect(page).toHaveURL(/case=1042/);

    await list.getByRole('button').nth(1).click();
    await expect(detail.getByRole('heading', { name: 'Roads' })).toBeVisible();
    // Only tabs with real data render.
    await expect(detail.getByRole('tab')).toHaveText(['Overview']);
    expect(requests.filter((r) => !r.startsWith('GET '))).toEqual([]);
});

test('Account 360 deep link scopes the explorer to that account', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 860 });
    await mockCasesApi(page);
    await page.goto('/dashboard/cases-intelligence/explorer?tenant_id=3');
    await expect(page.getByRole('combobox', { name: 'Account', exact: true })).toHaveValue('3');
    await expect(page.getByRole('list', { name: 'Cases' }).getByRole('button')).toHaveCount(1);
    const box = await page.locator('.nx-splitview-detail').boundingBox();
    expect(box.width).toBeGreaterThanOrEqual(420);
});

test('mobile explorer opens a full-screen case sheet with a way back', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockCasesApi(page);
    await page.goto('/dashboard/cases-intelligence/explorer');

    const list = page.getByRole('list', { name: 'Cases' });
    await expect(list.getByRole('button')).toHaveCount(2);
    // Nothing auto-opens on a phone.
    await expect(page.getByRole('article')).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);

    await list.getByRole('button').first().click();
    const sheet = page.getByRole('article');
    await expect(sheet.getByRole('heading', { name: 'Water Supply' })).toBeVisible();
    const box = await page.locator('.nx-splitview-detail').boundingBox();
    expect(Math.round(box.width)).toBe(390);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);

    await sheet.getByRole('button', { name: 'Back to cases' }).click();
    await expect(page.getByRole('article')).toHaveCount(0);
    await expect(page).not.toHaveURL(/case=/);
});
