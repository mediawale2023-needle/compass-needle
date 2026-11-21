import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock, apiPostMock, apiPatchMock, pushMock } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
    apiPostMock: vi.fn(),
    apiPatchMock: vi.fn(),
    pushMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
    apiGet: (path) => apiGetMock(path),
    apiPost: (path, body) => apiPostMock(path, body),
    apiPatch: (path, body) => apiPatchMock(path, body),
}));

const stableRouter = { push: pushMock };
const stableParams = { partnerId: '3' };
vi.mock('next/navigation', () => ({
    useRouter: () => stableRouter,
    useParams: () => stableParams,
    usePathname: () => '/dashboard/partners',
}));

vi.mock('next/link', () => ({
    default: ({ href, children, ...props }) => <a href={typeof href === 'string' ? href : '#'} {...props}>{children}</a>,
}));

import PartnersPage from '@/components/admin-domains/partners/PartnersPage';
import PartnerDetailPage from '@/components/admin-domains/partners/PartnerDetailPage';

const partner = (over = {}) => ({
    id: 3, name: 'Rajdhani Strategy', slug: 'rajdhani-strategy', brand_name: 'Rajdhani Strategy',
    brand_color: '#1F3A5F', brand_logo_url: null, show_powered_by: true, contact_email: 'ops@rajdhani.in',
    wholesale_price_inr: 15000, is_active: true, clients_active: 2, clients_paused: 1, legacy_requests: 1,
    billable_clients: 2, monthly_wholesale_inr: 30000, users_count: 1, created_at: '2026-11-01T10:00:00',
    ...over,
});

const seats = [
    { id: 1, client_label: 'Asha Patil', constituency: 'Belagavi South', seat_type: 'mla', status: 'active', tenant_id: 12, tenant_name: 'Asha Patil Office', notes: null, created_at: '2026-11-02T10:00:00' },
    { id: 2, client_label: 'Ravi Kulkarni', constituency: 'Pune Cantonment', seat_type: 'mla', status: 'requested', tenant_id: null, tenant_name: null, notes: 'Urgent before nominations', created_at: '2026-11-05T10:00:00' },
    { id: 3, client_label: 'Paused Client', constituency: '', seat_type: 'mp', status: 'paused', tenant_id: 14, tenant_name: 'Paused Office', notes: null, created_at: '2026-11-03T10:00:00' },
    { id: 4, client_label: 'Declined Client', constituency: '', seat_type: 'mp', status: 'rejected', tenant_id: null, tenant_name: null, notes: null, created_at: '2026-11-04T10:00:00' },
];

const users = [
    { id: 9, email: 'ops@rajdhani.in', display_name: 'Ops Lead', is_active: true, must_change_password: true, created_at: '2026-11-01T10:00:00' },
];

function mockDetailApi(over = {}) {
    apiGetMock.mockImplementation(async (path) => {
        if (over[path]) return over[path]();
        if (path === '/api/admin/partners') return { partners: [partner()] };
        if (path === '/api/admin/partners/3/seats') return { seats };
        if (path === '/api/admin/partners/3/users') return { users };
        if (path === '/api/admin/partners/available-tenants') return { tenants: [{ tenant_id: 21, name: 'Ravi Office', constituency: 'Pune', account_stage: 'aspirant', seat_type: 'mla' }] };
        throw new Error(`unexpected GET ${path}`);
    });
}

beforeEach(() => {
    [apiGetMock, apiPostMock, apiPatchMock, pushMock].forEach((m) => m.mockReset());
});

describe('Admin partners list', () => {
    const pendingReq = { id: 2, partner_id: 3, partner_name: 'Rajdhani Strategy', client_label: 'Ravi Kulkarni', constituency: 'Pune Cantonment', seat_type: 'mla', status: 'requested', notes: 'Urgent', created_at: '2026-11-05T10:00:00' };

    it('shows attributed-client totals, legacy requests and every partner', async () => {
        apiGetMock.mockImplementation(async (path) => path.endsWith('/requests/pending')
            ? { requests: [pendingReq] }
            : { partners: [partner(), partner({ id: 4, name: 'Bravo Campaigns', slug: 'bravo', clients_active: 1, clients_paused: 0, legacy_requests: 0, billable_clients: 1, monthly_wholesale_inr: 15000, is_active: false })] });
        render(<PartnersPage />);

        expect(await screen.findByRole('link', { name: 'Rajdhani Strategy' })).toHaveAttribute('href', '/dashboard/partners/3');
        expect(screen.getByRole('link', { name: 'Bravo Campaigns' })).toBeInTheDocument();
        expect(screen.getByText('Inactive')).toBeInTheDocument();
        // wholesale total = 2 active × 15,000 + 1 active × 15,000
        expect(screen.getByText('₹45,000')).toBeInTheDocument();
        expect(screen.getByText('Active attributed clients')).toBeInTheDocument();
        expect(screen.queryByText(/seat cap|seats used|awaiting activation/i)).toBeNull();

        const queue = screen.getByRole('region', { name: /legacy seat requests/i });
        expect(within(queue).getByText('Ravi Kulkarni')).toBeInTheDocument();
        expect(within(queue).getByRole('link', { name: 'Review' })).toHaveAttribute('href', '/dashboard/partners/3');
    });

    it('does not claim the queue is empty when it failed to load', async () => {
        apiGetMock.mockImplementation(async (path) => {
            if (path.endsWith('/requests/pending')) throw new Error('boom');
            return { partners: [partner()] };
        });
        render(<PartnersPage />);

        expect(await screen.findByText(/legacy request list unavailable/i)).toBeInTheDocument();
        expect(screen.queryByText(/no seat requests waiting/i)).toBeNull();
        expect(screen.getByRole('link', { name: 'Rajdhani Strategy' })).toBeInTheDocument();
    });

    it('shows an error with retry when partners cannot be loaded', async () => {
        apiGetMock.mockRejectedValueOnce(new Error('Server down')).mockRejectedValueOnce(new Error('Server down'));
        render(<PartnersPage />);
        expect(await screen.findByText(/data unavailable/i)).toBeInTheDocument();
        expect(screen.queryByText('No partners yet')).toBeNull();

        apiGetMock.mockImplementation(async (path) => (path.endsWith('/requests/pending') ? { requests: [] } : { partners: [partner()] }));
        fireEvent.click(screen.getByRole('button', { name: /try again/i }));
        expect(await screen.findByRole('link', { name: 'Rajdhani Strategy' })).toBeInTheDocument();
    });

    it('distinguishes zero partners from a failure', async () => {
        apiGetMock.mockImplementation(async (path) => (path.endsWith('/requests/pending') ? { requests: [] } : { partners: [] }));
        render(<PartnersPage />);
        expect(await screen.findByText('No partners yet')).toBeInTheDocument();
        expect(screen.queryByRole('region', { name: /legacy seat requests/i })).toBeNull();   // nothing legacy to show
    });

    it('creates a partner and opens its page', async () => {
        apiGetMock.mockImplementation(async (path) => (path.endsWith('/requests/pending') ? { requests: [] } : { partners: [] }));
        apiPostMock.mockResolvedValue({ partner: partner({ id: 8 }) });
        render(<PartnersPage />);
        await screen.findByText('No partners yet');

        fireEvent.click(screen.getByRole('button', { name: /new partner/i }));
        fireEvent.change(screen.getByLabelText(/consultancy name/i), { target: { value: 'Alpha Advisory' } });
        expect(screen.queryByLabelText(/seat cap/i)).toBeNull();   // no per-partner limit exists
        fireEvent.click(screen.getByRole('button', { name: /create partner/i }));

        await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith('/api/admin/partners', expect.objectContaining({
            name: 'Alpha Advisory', wholesale_price_inr: 15000, brand_name: null, brand_logo_url: null,
        })));
        expect(apiPostMock.mock.calls[0][1]).not.toHaveProperty('seat_cap');
        await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/dashboard/partners/8'));
    });

    it('shows the server message when creation is refused', async () => {
        apiGetMock.mockImplementation(async (path) => (path.endsWith('/requests/pending') ? { requests: [] } : { partners: [] }));
        apiPostMock.mockRejectedValue(new Error('brand_logo_url must be an https:// URL'));
        render(<PartnersPage />);
        await screen.findByText('No partners yet');
        fireEvent.click(screen.getByRole('button', { name: /new partner/i }));
        fireEvent.change(screen.getByLabelText(/consultancy name/i), { target: { value: 'Alpha Advisory' } });
        fireEvent.click(screen.getByRole('button', { name: /create partner/i }));
        expect(await screen.findByRole('alert')).toHaveTextContent(/https/);
        expect(pushMock).not.toHaveBeenCalled();
    });
});

describe('Admin partner detail', () => {
    it('offers the right action for each association status', async () => {
        mockDetailApi();
        render(<PartnerDetailPage />);
        const table = await screen.findByRole('region', { name: /partner client seats/i });

        const rowFor = (name) => within(table).getByText(name).closest('tr');
        expect(within(rowFor('Ravi Kulkarni')).getByRole('button', { name: 'Link (legacy)' })).toBeInTheDocument();
        expect(within(rowFor('Ravi Kulkarni')).getByRole('button', { name: 'Decline' })).toBeInTheDocument();
        expect(within(rowFor('Asha Patil')).getByRole('button', { name: 'Pause' })).toBeInTheDocument();
        expect(within(rowFor('Paused Client')).getByRole('button', { name: 'Resume' })).toBeInTheDocument();
        expect(within(rowFor('Declined Client')).queryByRole('button')).toBeNull();
        expect(within(rowFor('Asha Patil')).getByText(/Asha Patil Office/)).toBeInTheDocument();
    });

    it('links a legacy request to an unlinked account', async () => {
        mockDetailApi();
        apiPostMock.mockResolvedValue({ success: true });
        render(<PartnerDetailPage />);
        const table = await screen.findByRole('region', { name: /partner client seats/i });
        fireEvent.click(within(within(table).getByText('Ravi Kulkarni').closest('tr')).getByRole('button', { name: 'Link (legacy)' }));

        const select = await screen.findByLabelText(/customer account/i);
        expect(screen.getByRole('button', { name: /link and activate/i })).toBeDisabled();
        fireEvent.change(select, { target: { value: '21' } });
        fireEvent.click(screen.getByRole('button', { name: /link and activate/i }));

        await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith('/api/admin/partners/3/seats/2/activate', { tenant_id: 21 }));
        expect(await screen.findByText(/is now live/i)).toBeInTheDocument();
        // seats and partner counts are reloaded
        await waitFor(() => expect(apiGetMock.mock.calls.filter(([p]) => p === '/api/admin/partners/3/seats').length).toBeGreaterThan(1));
    });

    it('tells the operator when there is no account to link', async () => {
        mockDetailApi({ '/api/admin/partners/available-tenants': async () => ({ tenants: [] }) });
        render(<PartnerDetailPage />);
        const table = await screen.findByRole('region', { name: /partner client seats/i });
        fireEvent.click(within(within(table).getByText('Ravi Kulkarni').closest('tr')).getByRole('button', { name: 'Link (legacy)' }));

        expect(await screen.findByText(/no unlinked accounts available/i)).toBeInTheDocument();
        expect(screen.queryByLabelText(/customer account/i)).toBeNull();
        expect(screen.getByRole('link', { name: /open onboarding/i })).toHaveAttribute('href', '/dashboard/accounts/new');
    });

    it('shows the server error when activation is refused', async () => {
        mockDetailApi();
        apiPostMock.mockRejectedValue(new Error('Tenant is already linked to a partner seat'));
        render(<PartnerDetailPage />);
        const table = await screen.findByRole('region', { name: /partner client seats/i });
        fireEvent.click(within(within(table).getByText('Ravi Kulkarni').closest('tr')).getByRole('button', { name: 'Link (legacy)' }));
        fireEvent.change(await screen.findByLabelText(/customer account/i), { target: { value: '21' } });
        fireEvent.click(screen.getByRole('button', { name: /link and activate/i }));
        expect(await screen.findByRole('alert')).toHaveTextContent(/already linked/i);
    });

    it('asks for confirmation before declining a request', async () => {
        mockDetailApi();
        apiPostMock.mockResolvedValue({ success: true });
        render(<PartnerDetailPage />);
        const table = await screen.findByRole('region', { name: /partner client seats/i });
        fireEvent.click(within(within(table).getByText('Ravi Kulkarni').closest('tr')).getByRole('button', { name: 'Decline' }));

        expect(await screen.findByText(/decline ravi kulkarni\?/i)).toBeInTheDocument();
        expect(apiPostMock).not.toHaveBeenCalled();
        const confirmButtons = screen.getAllByRole('button', { name: 'Decline' });
        fireEvent.click(confirmButtons[confirmButtons.length - 1]);
        await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith('/api/admin/partners/3/seats/2/reject', {}));
    });

    it('pauses a live seat after confirmation', async () => {
        mockDetailApi();
        apiPostMock.mockResolvedValue({ success: true });
        render(<PartnerDetailPage />);
        const table = await screen.findByRole('region', { name: /partner client seats/i });
        fireEvent.click(within(within(table).getByText('Asha Patil').closest('tr')).getByRole('button', { name: 'Pause' }));
        const buttons = await screen.findAllByRole('button', { name: 'Pause' });
        fireEvent.click(buttons[buttons.length - 1]);
        await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith('/api/admin/partners/3/seats/1/status', { status: 'paused' }));
    });

    it('shows a new login\'s temporary password once and then forgets it', async () => {
        mockDetailApi();
        apiPostMock.mockResolvedValue({ success: true, email: 'new@rajdhani.in', temporary_password: 'Tmp9xYzABCde' });
        render(<PartnerDetailPage />);
        await screen.findByRole('region', { name: /partner logins/i });

        fireEvent.click(screen.getByRole('button', { name: /add login/i }));
        fireEvent.change(screen.getByLabelText(/work email/i), { target: { value: 'new@rajdhani.in' } });
        fireEvent.click(screen.getByRole('button', { name: /create login/i }));

        expect(await screen.findByTestId('temp-password')).toHaveTextContent('Tmp9xYzABCde');
        expect(apiPostMock).toHaveBeenCalledWith('/api/admin/partners/3/users', { email: 'new@rajdhani.in', display_name: null });
        fireEvent.click(screen.getByRole('button', { name: /i have saved it/i }));
        await waitFor(() => expect(screen.queryByTestId('temp-password')).toBeNull());
        expect(screen.queryByText('Tmp9xYzABCde')).toBeNull();
    });

    it('resets a password only after confirmation and shows the new one', async () => {
        mockDetailApi();
        apiPostMock.mockResolvedValue({ success: true, email: 'ops@rajdhani.in', temporary_password: 'Reset123Pass' });
        render(<PartnerDetailPage />);
        const logins = await screen.findByRole('region', { name: /partner logins/i });
        fireEvent.click(within(logins).getByRole('button', { name: /reset password/i }));
        expect(apiPostMock).not.toHaveBeenCalled();

        const buttons = await screen.findAllByRole('button', { name: /reset password/i });
        fireEvent.click(buttons[buttons.length - 1]);
        expect(await screen.findByTestId('temp-password')).toHaveTextContent('Reset123Pass');
        expect(apiPostMock).toHaveBeenCalledWith('/api/admin/partners/3/users/9/reset-password', {});
    });

    it('keeps the other panels usable when one panel fails to load', async () => {
        mockDetailApi({ '/api/admin/partners/3/seats': async () => { throw new Error('seats down'); } });
        render(<PartnerDetailPage />);
        expect(await screen.findByText(/seats down/i)).toBeInTheDocument();
        expect(screen.queryByText('No attributed clients yet')).toBeNull();
        expect(await screen.findByRole('region', { name: /partner logins/i })).toBeInTheDocument();
    });

    it('says so when the partner does not exist', async () => {
        mockDetailApi({ '/api/admin/partners': async () => ({ partners: [partner({ id: 99 })] }) });
        render(<PartnerDetailPage />);
        expect(await screen.findByText(/this partner does not exist/i)).toBeInTheDocument();
    });

    it('deactivates the partner only after confirmation', async () => {
        mockDetailApi();
        apiPatchMock.mockResolvedValue({ success: true });
        render(<PartnerDetailPage />);
        fireEvent.click(await screen.findByRole('button', { name: /deactivate partner/i }));
        expect(apiPatchMock).not.toHaveBeenCalled();
        // The login row also has a "Deactivate" button, so scope to the confirmation dialog.
        const overlay = await waitFor(() => {
            const el = document.querySelector('.modal-overlay');
            expect(el).not.toBeNull();
            return el;
        });
        fireEvent.click(within(overlay).getByRole('button', { name: 'Deactivate' }));
        await waitFor(() => expect(apiPatchMock).toHaveBeenCalledWith('/api/admin/partners/3', { is_active: false }));
    });

    it('has no seat-cap control, metric or warning, and saves branding and pricing as numbers', async () => {
        mockDetailApi();
        apiPatchMock.mockResolvedValue({ success: true });
        render(<PartnerDetailPage />);
        const price = await screen.findByLabelText(/wholesale/i);
        expect(screen.queryByLabelText(/seat cap/i)).toBeNull();
        expect(screen.queryByText(/seats used|seat cap|cap reached/i)).toBeNull();
        expect(screen.getByText('Active clients')).toBeInTheDocument();
        expect(screen.getByText('Paused clients')).toBeInTheDocument();
        fireEvent.change(price, { target: { value: '18000' } });
        fireEvent.click(screen.getByRole('button', { name: /save settings/i }));
        await waitFor(() => expect(apiPatchMock).toHaveBeenCalledWith('/api/admin/partners/3', expect.objectContaining({
            wholesale_price_inr: 18000, brand_color: '#1F3A5F',
        })));
        expect(apiPatchMock.mock.calls[0][1]).not.toHaveProperty('seat_cap');
    });
});
