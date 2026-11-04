import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock } = vi.hoisted(() => ({ apiGetMock: vi.fn() }));

vi.mock('@/lib/api', () => ({ apiGet: (path) => apiGetMock(path) }));
vi.mock('next/link', () => ({
    default: ({ href, children, ...props }) => <a href={typeof href === 'string' ? href : '#'} {...props}>{children}</a>,
}));

import DashboardOverview from '@/app/dashboard/page';

const NOW_ISO = new Date().toISOString().slice(0, 19);

const healthyWhatsApp = {
    status: 'amber',
    reason: '1 active tenant(s) have incomplete WhatsApp routing.',
    meta_token: { configured: true, status: 'green', detail: 'Authenticated as Needle.' },
    webhook: { status: 'green', last_webhook: NOW_ISO, inbound_queue: { received_count: 2, processing_count: 1, failed_count: 0, stale_received_count: 0, stale_processing_count: 0 } },
    routing: { status: 'amber', active_tenants: 2, configured_tenants: 1, misconfigured_tenants: 1, tenant_issues: [{ tenant_id: 2, name: 'Priya Nair', constituency: 'Thrissur', issue: 'missing Meta phone number ID' }] },
    outbound: { status: 'green', failed_outbound_24h: 0, sent_outbound_24h: 9 },
};

function routes(overrides = {}) {
    return async (path) => {
        const table = {
            '/api/admin/stats': { total_accounts: 2, total_mps: 2, total_cases: 14 },
            '/api/admin/mps': { mps: [
                { tenant_id: 1, display_name: 'Arun Kumar', username: 'mp_arun', parliamentary_constituency: 'Bangalore North', whatsapp_number: '+919000000001', created_at: '2026-01-01', profile: { constituency: 'Bangalore North', state: 'Karnataka' } },
                { tenant_id: 2, display_name: 'Priya Nair', username: 'mp_priya', parliamentary_constituency: 'Thrissur', whatsapp_number: '+919000000002', created_at: '2026-01-02', profile: { constituency: 'Thrissur', state: 'Kerala' } },
            ] },
            '/api/admin/alerts': { alerts: [
                { type: 'whatsapp_health', severity: 'warning', title: 'WhatsApp needs review', description: 'generic' },
                { type: 'setup_incomplete', severity: 'info', tenant_id: 1, title: 'Arun Kumar — setup incomplete', description: 'Launch steps pending' },
            ] },
            '/api/admin/system-health': { last_checked: NOW_ISO, whatsapp: healthyWhatsApp, openai: { status: 'green', configured: true }, gemini: { status: 'red', configured: false } },
            '/api/admin/whatsapp/inbound?limit=1': { rows: [], total: 0, summary: { received_count: 2, processing_count: 1, failed_count: 0, stale_received_count: 0, stale_processing_count: 0, last_webhook: NOW_ISO } },
            '/api/admin/jobs?page=1&page_size=10': { items: [], summary: { running: 0, failed: 1, success: 4, queued: 0 } },
            '/api/admin/audit?days=7': { entries: [{ id: 1, action: 'staff.create', admin_username: 'ananya', target_type: 'staff', created_at: NOW_ISO }] },
            '/api/admin/cases/aggregates?weeks=12': {
                open_now: 5,
                open_by_tenant: { 1: { open: 4, open_over_14_days: 2 }, 2: { open: 1, open_over_14_days: 0 } },
                ageing: [
                    { label: '0–3 days', min_days: 0, max_days: 3, count: 2 },
                    { label: '4–7 days', min_days: 4, max_days: 7, count: 1 },
                    { label: '8–14 days', min_days: 8, max_days: 14, count: 0 },
                    { label: '15–30 days', min_days: 15, max_days: 30, count: 1 },
                    { label: 'Over 30 days', min_days: 31, max_days: null, count: 1 },
                ],
                weekly: [
                    { week_start: '2026-09-28', new: 3, resolved: 1, open_at_end: 4 },
                    { week_start: '2026-10-05', new: 2, resolved: 1, open_at_end: 5 },
                ],
                resolution: { resolved_in_window: 2, median_hours: 60 },
            },
            '/api/admin/tenant-health': { tenants: [{ tenant_id: 1, last_case: NOW_ISO }] },
            '/api/admin/parliament/sync/status': { tenants: [{ parliament_last_synced: NOW_ISO, parliament_sync_status: 'synced' }] },
            ...overrides,
        };
        if (path in table) {
            const value = table[path];
            if (value instanceof Error) throw value;
            return value;
        }
        throw new Error(`unexpected ${path}`);
    };
}

describe('Command Centre', () => {
    beforeEach(() => {
        apiGetMock.mockReset();
        apiGetMock.mockImplementation(routes());
    });

    it('renders the approved sections from real API data', async () => {
        render(<DashboardOverview />);
        expect(screen.getByRole('heading', { name: 'Command Centre' })).toBeInTheDocument();
        expect((await screen.findAllByText('Arun Kumar')).length).toBeGreaterThan(0);
        for (const title of ['Needs your attention', 'Accounts', 'Cases', 'Operational pulse', 'Case intake vs resolution', 'Case ageing', 'Account health', 'Platform health', 'Recent activity']) {
            expect(screen.getByRole('heading', { name: new RegExp(`^${title}`) })).toBeInTheDocument();
        }
        expect(screen.getByRole('link', { name: 'Create account' })).toHaveAttribute('href', '/dashboard/accounts/new');
        // Real aggregate numbers, not mock fixtures.
        expect(screen.getByText('2.5 days')).toBeInTheDocument();
        expect(screen.getByText('Over 30 days')).toBeInTheDocument();
        expect(screen.getByText(/2 older than 14 days/)).toBeInTheDocument();
    });

    it('replaces the generic WhatsApp alert with precise, real incidents and actions', async () => {
        render(<DashboardOverview />);
        await screen.findAllByText('Arun Kumar');
        const queue = document.getElementById('attention');
        await within(queue).findByText('WhatsApp routing incomplete');
        expect(within(queue).queryByText('WhatsApp needs review')).not.toBeInTheDocument();
        expect(within(queue).getByRole('link', { name: 'Fix WhatsApp routing' })).toHaveAttribute('href', '/dashboard/mps/2#whatsapp');
        expect(within(queue).getByRole('link', { name: 'Resume setup' })).toHaveAttribute('href', '/dashboard/mps/1/setup');
        expect(screen.queryByText(/reconnect/i)).not.toBeInTheDocument();
    });

    it('represents an invalid global Meta token as one platform-wide incident', async () => {
        apiGetMock.mockImplementation(routes({
            '/api/admin/system-health': { last_checked: NOW_ISO, whatsapp: { ...healthyWhatsApp, status: 'red', meta_token: { configured: true, status: 'red', detail: 'Error validating access token' }, routing: { ...healthyWhatsApp.routing, tenant_issues: [], misconfigured_tenants: 0, configured_tenants: 2, status: 'green' } }, openai: { configured: true }, gemini: { configured: true } },
        }));
        render(<DashboardOverview />);
        const queue = document.getElementById('attention');
        expect(await within(queue).findByText('Meta access token invalid')).toBeInTheDocument();
        expect(within(queue).getAllByText('All WhatsApp accounts').length).toBeGreaterThan(0);
        expect(within(queue).queryByRole('link', { name: 'Open account' })).not.toBeInTheDocument();
        expect(within(queue).getByRole('link', { name: 'Open Messaging' })).toHaveAttribute('href', '/dashboard/system/whatsapp');
    });

    it('filters the queue by severity', async () => {
        render(<DashboardOverview />);
        const queue = document.getElementById('attention');
        await within(queue).findByText('WhatsApp routing incomplete');
        fireEvent.click(within(queue).getByRole('tab', { name: /Review/ }));
        expect(within(queue).getByText('Arun Kumar — setup incomplete')).toBeInTheDocument();
        expect(within(queue).queryByText('WhatsApp routing incomplete')).not.toBeInTheDocument();
    });

    it('never claims AI providers are operational from key configuration alone', async () => {
        render(<DashboardOverview />);
        await screen.findAllByText('Arun Kumar');
        expect(screen.getByText('Not configured')).toBeInTheDocument();
        expect(screen.getAllByText('Key configuration only — not a live check')).toHaveLength(2);
    });

    it('distinguishes unavailable operational data from an empty or healthy state', async () => {
        apiGetMock.mockRejectedValue(new Error('Admin API unavailable'));
        render(<DashboardOverview />);

        expect((await screen.findAllByText('Data unavailable')).length).toBeGreaterThan(1);
        const summary = screen.getByRole('region', { name: 'Summary' });
        // Attention total + Critical + Warning + Review + Accounts + Open cases:
        // each says so instead of rendering a zero it cannot substantiate.
        expect(within(summary).getAllByText('Unavailable')).toHaveLength(6);
        expect(screen.queryByText('No active alerts')).not.toBeInTheDocument();
        expect(screen.queryByText(/Operational$/)).not.toBeInTheDocument();
    });
});
