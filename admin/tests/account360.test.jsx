import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock, apiPostMock, apiPatchMock } = vi.hoisted(() => ({ apiGetMock: vi.fn(), apiPostMock: vi.fn(), apiPatchMock: vi.fn() }));
vi.mock('@/lib/api', () => ({
    apiGet: (p) => apiGetMock(p),
    apiPost: (p, b) => apiPostMock(p, b),
    apiPatch: (p, b) => apiPatchMock(p, b),
}));
vi.mock('next/link', () => ({ default: ({ href, children, ...props }) => <a href={href} {...props}>{children}</a> }));

import Account360Page from '@/components/admin-domains/accounts/account360/Account360Page';

const NOW = new Date().toISOString().slice(0, 19);
const DETAIL = {
    tenant_id: 9, seat_type: 'mp', account_stage: 'elected', last_login: NOW,
    profile: { mp_name: 'Avichal Dubey', constituency: 'Udaipur', state: 'Rajasthan', house: 'Lok Sabha', party: 'Independent', whatsapp_number: '+919000000009', phone_number_id: '', key_facts: ['Tribal belt'], languages: ['Hindi'], created_at: '2026-03-12T00:00:00' },
    cases: { total: 140, open: 30, resolved: 100, last_case: NOW },
    staff: [{ id: 1, username: 'pa_ravi', display_name: 'Ravi Meena', role: 'staff', is_active: true, phone: '', last_login: NOW }],
    onboarding_state: {},
    activity: [{ activity_type: 'draft_letter', title: 'Drafted a letter to PHED', created_at: NOW }],
};

function healthWith(overrides = {}) {
    return {
        whatsapp: {
            meta_token: { configured: true, status: 'green' },
            routing: { status: 'amber', tenant_issues: [{ tenant_id: 9, name: 'Avichal Dubey', issue: 'missing Meta phone number ID' }] },
            outbound: { status: 'green' }, webhook: { status: 'green' },
            ...overrides,
        },
    };
}

function routes(extra = {}) {
    const table = {
        '/api/admin/mps/9/detail': DETAIL,
        '/api/admin/mps/9/notes': { notes: [{ id: 1, body: 'Prefers Hindi replies', admin_username: 'ananya', created_at: NOW }] },
        '/api/admin/mps/9/support-access': { requests: [{ request_key: 'rk1', status: 'approved', reason: 'Debug', duration_minutes: 30, requested_at: NOW, target_username: 'avichal' }] },
        '/api/admin/mps/9/geography': { assemblies: { 'Udaipur Rural': ['Kheda', 'Badgaon'] } },
        '/api/admin/cases/aggregates?weeks=12&tenant_id=9': {
            open_now: 30, open_by_tenant: {}, open_by_category: [{ category: 'Water Supply', count: 12 }, { category: 'Roads', count: 8 }],
            ageing: [{ label: '0–3 days', min_days: 0, count: 20 }, { label: '15–30 days', min_days: 15, count: 10 }],
            weekly: [{ week_start: '2026-09-21', new: 9, resolved: 7, open_at_end: 27 }, { week_start: '2026-09-28', new: 8, resolved: 6, open_at_end: 29 }, { week_start: '2026-10-05', new: 3, resolved: 2, open_at_end: 30 }],
            resolution: { resolved_in_window: 13, median_hours: 96 },
        },
        '/api/admin/system-health': healthWith(),
        '/api/admin/whatsapp/outbound?tenant_id=9&page=1&page_size=100': { items: [{ id: 5, tenant_id: 9, status: 'sent', message_body: 'Your case is registered', created_at: NOW }] },
        '/api/admin/alerts': { alerts: [] },
        '/api/admin/parliament/sync/status': { tenants: [{ tenant_id: 9, parliament_sync_status: 'synced', parliament_sync_enabled: true, parliament_last_synced: NOW }] },
        '/api/admin/seats/geography-decisions?seat_key=mp%3AUdaipur&limit=30': { items: [{ case_id: 1, needs_review: true, location: 'Nayakheda', review_reason: 'No match', created_at: NOW }, { case_id: 2, resolved: true, matched_value: 'Kheda' }] },
        ...extra,
    };
    return async (path) => {
        if (path in table) {
            const value = table[path];
            if (value instanceof Error) throw value;
            return value;
        }
        throw new Error(`unexpected ${path}`);
    };
}

async function renderPage() {
    render(<Account360Page tenantId="9" />);
    await screen.findByRole('heading', { name: 'Avichal Dubey', level: 1 });
}

describe('Account 360', () => {
    beforeEach(() => {
        window.history.replaceState(null, '', '/dashboard/mps/9');
        apiGetMock.mockReset(); apiPostMock.mockReset(); apiPatchMock.mockReset();
        apiGetMock.mockImplementation(routes());
    });

    it('shows identity, account condition and six readiness areas from real data', async () => {
        await renderPage();
        expect(screen.getByText('MP · Lok Sabha · Elected')).toBeInTheDocument();
        expect(within(screen.getByRole('region', { name: 'Account' })).getByText(/Udaipur · Rajasthan/)).toBeInTheDocument();
        expect(screen.getByText('Tenant #9')).toBeInTheDocument();
        expect(await screen.findByText('Condition: Warning')).toBeInTheDocument();
        expect(screen.queryByText(/owner/i)).not.toBeInTheDocument();
        const readiness = screen.getByRole('heading', { name: 'Account readiness' }).closest('section');
        for (const label of ['WhatsApp', 'Onboarding', 'Staff', 'Geography', 'Intelligence', 'Cases']) expect(within(readiness).getByText(label)).toBeInTheDocument();
        expect(within(readiness).getByText('Routing incomplete')).toBeInTheDocument();
        expect(within(readiness).getByText('30 open')).toBeInTheDocument();
        expect(screen.queryByText(/village|SLA|quality rating/i)).not.toBeInTheDocument();
    });

    it('leads with the account-specific routing incident and opens the real fix', async () => {
        await renderPage();
        const fix = await screen.findAllByRole('button', { name: 'Fix WhatsApp routing' });
        fireEvent.click(fix[0]);
        expect(screen.getByRole('heading', { name: 'WhatsApp configuration' })).toBeInTheDocument();
        expect(screen.getByLabelText('WhatsApp number', { exact: false })).toHaveValue('+919000000009');
        expect(window.location.hash).toBe('#whatsapp');
    });

    it('treats a global Meta token failure as platform-wide, not this account', async () => {
        apiGetMock.mockImplementation(routes({
            '/api/admin/system-health': healthWith({ meta_token: { configured: true, status: 'red' }, routing: { status: 'green', tenant_issues: [] } }),
        }));
        await renderPage();
        expect(await screen.findByText(/This affects every account and is not specific to this one/)).toBeInTheDocument();
        expect(await screen.findByText('No account issues')).toBeInTheDocument();
        expect(screen.queryByText(/reconnect/i)).not.toBeInTheDocument();
    });

    it('preserves WhatsApp save with the existing validation', async () => {
        apiPatchMock.mockResolvedValue({});
        window.history.replaceState(null, '', '/dashboard/mps/9#whatsapp');
        await renderPage();
        fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
        fireEvent.change(screen.getByLabelText('WhatsApp number', { exact: false }), { target: { value: '919000' } });
        fireEvent.click(screen.getByRole('button', { name: 'Save' }));
        expect(await screen.findByText('Number must start with + (e.g. +919876543210)')).toBeInTheDocument();
        expect(apiPatchMock).not.toHaveBeenCalled();
        fireEvent.change(screen.getByLabelText('WhatsApp number', { exact: false }), { target: { value: '+919000000009' } });
        fireEvent.change(screen.getByLabelText('Meta phone number ID', { exact: false }), { target: { value: '123456' } });
        await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Save' })); });
        expect(apiPatchMock).toHaveBeenCalledWith('/api/admin/mps/9/whatsapp', { whatsapp_number: '+919000000009', phone_number_id: '123456' });
    });

    it('preserves adding staff', async () => {
        apiPostMock.mockResolvedValue({});
        window.history.replaceState(null, '', '/dashboard/mps/9#staff');
        await renderPage();
        expect(screen.getByText('Ravi Meena')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Add staff' }));
        fireEvent.change(screen.getByLabelText('Username', { exact: false }), { target: { value: 'pa_new' } });
        fireEvent.change(screen.getByLabelText('Password', { exact: false }), { target: { value: 'Secret123!' } });
        await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Create staff account' })); });
        expect(apiPostMock).toHaveBeenCalledWith('/api/admin/staff', expect.objectContaining({ tenant_id: 9, username: 'pa_new', password: 'Secret123!', role: 'staff' }));
    });

    it('preserves admin notes and activity', async () => {
        apiPostMock.mockResolvedValue({});
        window.history.replaceState(null, '', '/dashboard/mps/9#activity');
        await renderPage();
        expect(screen.getByText('Drafted a letter to PHED')).toBeInTheDocument();
        expect(await screen.findByText('Prefers Hindi replies')).toBeInTheDocument();
        fireEvent.change(screen.getByLabelText('Add a note about this account'), { target: { value: 'Called the PA' } });
        await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Add note' })); });
        expect(apiPostMock).toHaveBeenCalledWith('/api/admin/mps/9/notes', { body: 'Called the PA' });
    });

    it('preserves support access request, launch and cancel, and profile/password editing', async () => {
        apiPostMock.mockImplementation(async (path) => (path.endsWith('/launch') ? { request_key: 'rk1', launch_token: 'tok' } : {}));
        const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
        window.history.replaceState(null, '', '/dashboard/mps/9#profile');
        await renderPage();
        expect(screen.getByRole('link', { name: 'Edit profile, constituency & password' })).toHaveAttribute('href', '/dashboard/accounts/registry?tenant_id=9');
        expect(document.getElementById('profile')).not.toBeNull();
        await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Request access' })); });
        expect(apiPostMock).toHaveBeenCalledWith('/api/admin/mps/9/support-access/request', { reason: 'Investigating an operator issue in the tenant workspace.', duration_minutes: 30 });
        await act(async () => { fireEvent.click(await screen.findByRole('button', { name: 'Open tenant view' })); });
        expect(apiPostMock).toHaveBeenCalledWith('/api/admin/support-access/rk1/launch', {});
        expect(openSpy).toHaveBeenCalledWith(expect.stringContaining('request=rk1&launch_token=tok'), '_blank', 'noopener,noreferrer');
        await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Cancel' })); });
        expect(apiPostMock).toHaveBeenCalledWith('/api/admin/support-access/rk1/cancel', {});
        openSpy.mockRestore();
    });

    it('shows real geography decisions and parliament freshness', async () => {
        window.history.replaceState(null, '', '/dashboard/mps/9#geography');
        await renderPage();
        expect(await screen.findByText('“Nayakheda”')).toBeInTheDocument();
        expect(screen.getByText('Udaipur Rural')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Open geography workspace' })).toHaveAttribute('href', '/dashboard/shared-geography/workspace?tenant_id=9');
        fireEvent.click(screen.getByRole('link', { name: 'Intelligence' }));
        expect(screen.getByText('Parliament questions & answers')).toBeInTheDocument();
        expect(screen.getByText(/not reported per account/)).toBeInTheDocument();
    });

    it('keeps sections usable when secondary sources fail', async () => {
        apiGetMock.mockImplementation(routes({
            '/api/admin/system-health': new Error('down'),
            '/api/admin/cases/aggregates?weeks=12&tenant_id=9': new Error('down'),
            '/api/admin/parliament/sync/status': new Error('down'),
            '/api/admin/whatsapp/outbound?tenant_id=9&page=1&page_size=100': new Error('down'),
            '/api/admin/alerts': new Error('down'),
        }));
        await renderPage();
        expect(await screen.findByText('Condition unavailable')).toBeInTheDocument();
        expect(await screen.findByText('Case aggregates could not be loaded.')).toBeInTheDocument();
    });
});
