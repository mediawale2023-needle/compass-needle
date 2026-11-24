import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { vi } from 'vitest';

const { replaceMock, pushMock, sessionState, apiMocks } = vi.hoisted(() => ({
    replaceMock: vi.fn(),
    pushMock: vi.fn(),
    sessionState: { current: null },
    apiMocks: {
        partnerClients: vi.fn(),
        partnerClientSummary: vi.fn(),
        partnerClientReport: vi.fn(),
        partnerClientOverview: vi.fn(),
    },
}));

// Next's real router object is referentially stable; a fresh object per render would retrigger effects.
const stableRouter = { replace: replaceMock, push: pushMock };
const stableParams = { seatId: '7' };
vi.mock('next/navigation', () => ({
    useRouter: () => stableRouter,
    useParams: () => stableParams,
}));
vi.mock('@/lib/partnerSession', () => ({
    usePartnerSession: () => sessionState.current,
}));
vi.mock('@/lib/partnerApi', () => apiMocks);

import PartnerDashboardPage from '@/app/partner/dashboard/page';
import PartnerClientPage from '@/app/partner/dashboard/clients/[seatId]/page';
import PartnerLoginPage from '@/app/partner/page';
import PartnerClientsPage from '@/app/partner/dashboard/clients/page';

const summary = (over = {}) => ({
    total: 40, resolved: 30, open: 10, critical: 3, resolution_rate: 0.75, avg_resolution_days: 2.4, ...over,
});

const weeks = Array.from({ length: 8 }, (_, i) => ({ period_start: `2026-11-0${1 + i}`, period_end: `2026-11-${10 + i}`, received: 10 + i, resolved: 5 + i }));
const clientsPayload = (over = {}) => ({
    days: 30, active_clients: 2, window: { kind: 'days', from: '2026-10-19', to: '2026-11-17', days: 30 },
    portfolio: { total: 52, resolved: 36, open: 16, critical: 9, trend: weeks, bucket_days: 7 },
    clients: [
        { id: 7, client_label: 'Asha Patil', constituency: 'Belagavi South', seat_type: 'mla', status: 'active', summary: summary() },
        { id: 8, client_label: 'Ravi Kulkarni', constituency: 'Pune Cantonment', seat_type: 'mp', status: 'active', summary: summary({ total: 12, resolved: 6, open: 6, critical: 6, resolution_rate: 0.5 }) },
        { id: 9, client_label: 'Old Client', constituency: '', seat_type: 'mp', status: 'paused', summary: null },
    ],
    ...over,
});

const overviewPayload = (over = {}) => ({
    client: { id: 7, client_label: 'Asha Patil' },
    overview: {
        mode: 'partner', seat: 'Belagavi', date_label: 'Today',
        attention_counts: [
            { key: 'needs_review', label: 'Needs review', value: 4, tone: 'red' },
            { key: 'needs_location', label: 'Needs location', value: 2, tone: 'amber' },
            { key: 'sync_issues', label: 'Sync issues', value: 1, tone: 'rust' },
            { key: 'govt_updates', label: 'Govt updates', value: 3, tone: 'green' },
            { key: 'ready_to_file', label: 'Ready to file', value: 6, tone: 'green' },
        ],
        government_tracking: {
            ready: 6, submitted: 5, registered: 7, forwarded: 2, awaiting_action: 8, resolved: 11,
            disposed: 1, rejected: 3, awaiting_verification: 9, sync_issues: 1,
        },
        constituency_pressure: [{ name: 'Bailhongal', count: 12 }],
        issue_pressure: [{ title: 'Water supply', count: 14 }],
        office_pending: [
            { key: 'letters', label: 'New letters awaiting intake review', value: 5 },
            { key: 'drafts', label: 'Drafts awaiting MP approval', value: 2 },
            { key: 'unassigned', label: 'Cases needing an owner', value: 13 },
        ],
        validation: { thread_count: 40, counts_only: true },
        ...over,
    },
});

async function openTab(name) {
    await screen.findByRole('heading', { name: 'Asha Patil', level: 1 });
    fireEvent.click(screen.getByRole('tab', { name }));
}
const table = () => screen.getByRole('table');
const rowFor = (label) => within(table()).getByText(label).closest('tr');

function signedIn(over = {}) {
    sessionState.current = {
        ready: true, token: 'tok', mustChangePassword: false,
        partner: { brand_name: 'Rajdhani Strategy' },
        signIn: vi.fn(), changePassword: vi.fn(), signOut: vi.fn(),
        ...over,
    };
}

beforeEach(() => {
    Object.values(apiMocks).forEach((m) => m.mockReset());
    apiMocks.partnerClients.mockResolvedValue(clientsPayload());
    replaceMock.mockReset();
    pushMock.mockReset();
    signedIn();
});

describe('partner portfolio page', () => {
    it('shows portfolio totals and one row per client, with only live clients openable', async () => {
        render(<PartnerDashboardPage />);
        await screen.findByRole('table');

        expect(screen.getByText('Across 2 active clients')).toBeInTheDocument();
        const totals = screen.getByRole('region', { name: /portfolio totals/i });
        expect(within(totals).getByText('52')).toBeInTheDocument();
        expect(within(totals).getByText('69.2')).toBeInTheDocument(); // 36 of 52 resolved

        expect(within(rowFor('Old Client')).getByText('Paused')).toBeInTheDocument();
        expect(within(rowFor('Ravi Kulkarni')).getByText('Needs attention')).toBeInTheDocument();
        expect(within(rowFor('Asha Patil')).getByText('Watch')).toBeInTheDocument();

        expect(screen.getByRole('link', { name: /open asha patil/i })).toHaveAttribute('href', '/partner/dashboard/clients/7');
        expect(screen.getByRole('link', { name: /open ravi kulkarni/i })).toHaveAttribute('href', '/partner/dashboard/clients/8');
        expect(screen.queryByRole('link', { name: /open old client/i })).toBeNull();
    });

    it('ranks clients that need attention and leaves out paused ones', async () => {
        render(<PartnerDashboardPage />);
        const panel = await screen.findByRole('region', { name: /needs attention/i });
        const names = within(panel).getAllByRole('link').map((a) => a.textContent);
        expect(names[0]).toMatch(/Ravi Kulkarni/);
        expect(names.join(' ')).not.toMatch(/Old Client/);
    });

    it('draws the portfolio trend chart from aggregate counts with an accessible description', async () => {
        render(<PartnerDashboardPage />);
        const chart = await screen.findByRole('img', { name: /portfolio grievances by week/i });
        expect(chart.getAttribute('aria-label')).toContain('2026-11-08 to 2026-11-17: 17 received, 12 resolved');
    });

    it('searches, filters and sorts the client table', async () => {
        render(<PartnerDashboardPage />);
        await screen.findByRole('table');
        fireEvent.change(screen.getByPlaceholderText(/search client/i), { target: { value: 'pune' } });
        expect(within(table()).queryByText('Asha Patil')).toBeNull();
        expect(within(table()).getByText('Ravi Kulkarni')).toBeInTheDocument();

        fireEvent.change(screen.getByPlaceholderText(/search client/i), { target: { value: '' } });
        fireEvent.click(within(screen.getByRole('group', { name: /filter clients/i })).getByRole('button', { name: /^paused/i }));
        expect(within(table()).getByText('Old Client')).toBeInTheDocument();
        expect(within(table()).queryByText('Asha Patil')).toBeNull();

        fireEvent.click(within(screen.getByRole('group', { name: /filter clients/i })).getByRole('button', { name: /^all/i }));
        fireEvent.click(screen.getByRole('button', { name: /resolution rate/i }));
        const first = within(table()).getAllByRole('row')[1];
        expect(first).toHaveTextContent('Asha Patil'); // 75% before 50%
    });

    it('refetches when the period changes', async () => {
        render(<PartnerDashboardPage />);
        await screen.findByRole('table');
        fireEvent.click(screen.getByRole('button', { name: '90 days' }));
        await waitFor(() => expect(apiMocks.partnerClients).toHaveBeenLastCalledWith({ kind: 'days', days: 90 }));
    });

    it('offers all-time and a custom date range, and queries the API with them', async () => {
        render(<PartnerDashboardPage />);
        await screen.findByRole('table');
        fireEvent.click(screen.getByRole('button', { name: 'All time' }));
        await waitFor(() => expect(apiMocks.partnerClients).toHaveBeenLastCalledWith({ kind: 'all' }));
        expect(screen.getByRole('button', { name: 'All time' })).toHaveAttribute('aria-pressed', 'true');

        fireEvent.click(screen.getByRole('button', { name: 'Custom' }));
        const dialog = screen.getByRole('dialog', { name: /custom date range/i });
        fireEvent.change(within(dialog).getByLabelText('From'), { target: { value: '2025-03-01' } });
        fireEvent.change(within(dialog).getByLabelText('To'), { target: { value: '2025-01-01' } });
        fireEvent.submit(dialog); // bypass the browser's own min/max check to exercise ours
        expect(within(dialog).getByRole('alert')).toHaveTextContent(/on or before/i);

        fireEvent.change(within(dialog).getByLabelText('To'), { target: { value: '2025-06-30' } });
        fireEvent.click(within(dialog).getByRole('button', { name: /apply range/i }));
        await waitFor(() => expect(apiMocks.partnerClients).toHaveBeenLastCalledWith({ kind: 'custom', from: '2025-03-01', to: '2025-06-30' }));
        expect(screen.getByRole('button', { name: /1 Mar 2025 – 30 Jun 2025/ })).toHaveAttribute('aria-pressed', 'true');
    });

    it('labels an all-time portfolio with the date history starts from', async () => {
        apiMocks.partnerClients.mockResolvedValue(clientsPayload({ window: { kind: 'all', from: '2024-05-03', to: '2026-11-24', days: 935 } }));
        render(<PartnerDashboardPage />);
        expect(await screen.findByText(/All time \(since 3 May 2024\)/)).toBeInTheDocument();
    });

    it('shows an unavailable state, not zeros, when the API fails, and retries', async () => {
        apiMocks.partnerClients.mockReset();
        apiMocks.partnerClients.mockRejectedValueOnce(Object.assign(new Error('Could not reach the server.'), { status: 0 }));
        render(<PartnerDashboardPage />);

        expect(await screen.findByRole('alert')).toHaveTextContent(/unavailable right now/i);
        expect(screen.queryByRole('region', { name: /portfolio totals/i })).toBeNull();

        apiMocks.partnerClients.mockResolvedValueOnce(clientsPayload());
        fireEvent.click(screen.getByRole('button', { name: /retry/i }));
        expect(await screen.findByRole('table')).toBeInTheDocument();
    });

    it('distinguishes an empty portfolio from a failed load', async () => {
        apiMocks.partnerClients.mockResolvedValue(clientsPayload({
            active_clients: 0, clients: [], portfolio: { total: 0, resolved: 0, open: 0, critical: 0, trend: [], bucket_days: 7 },
        }));
        render(<PartnerDashboardPage />);
        expect(await screen.findByText('No clients yet')).toBeInTheDocument();
        expect(screen.queryByText(/unavailable/i)).toBeNull();
    });

    it('has no seat-request form, seat-cap indicator or cap warning', async () => {
        render(<PartnerDashboardPage />);
        await screen.findByRole('table');
        expect(screen.queryByRole('button', { name: /request client seat/i })).toBeNull();
        expect(screen.queryByText(/seat cap|seats used|awaiting activation|raise/i)).toBeNull();
    });

    it('lists any number of attributed clients without limiting or warning', async () => {
        const many = Array.from({ length: 40 }, (_, i) => ({
            id: 100 + i, client_label: `Client ${i}`, constituency: 'X', seat_type: 'mla', status: 'active', summary: summary(),
        }));
        apiMocks.partnerClients.mockResolvedValue(clientsPayload({ active_clients: 40, clients: many }));
        render(<PartnerClientsPage />);
        await screen.findByRole('table');
        expect(screen.getAllByRole('link', { name: /^open client/i })).toHaveLength(40);
        expect(screen.getByText('Showing 40 of 40 clients')).toBeInTheDocument();
        expect(screen.queryByRole('alert')).toBeNull();
    });

    it('sends signed-out visitors to the sign-in page without calling the API', async () => {
        signedIn({ token: null });
        render(<PartnerDashboardPage />);
        await waitFor(() => expect(replaceMock).toHaveBeenCalledWith('/partner'));
        expect(apiMocks.partnerClients).not.toHaveBeenCalled();
    });

    it('sends users who still owe a password change back to sign-in', async () => {
        signedIn({ mustChangePassword: true });
        render(<PartnerDashboardPage />);
        await waitFor(() => expect(replaceMock).toHaveBeenCalledWith('/partner'));
        expect(apiMocks.partnerClients).not.toHaveBeenCalled();
    });
});

describe('partner client page', () => {
    const detail = {
        client: { id: 7, client_label: 'Asha Patil', constituency: 'Belagavi South', seat_type: 'mla', status: 'active' },
        summary: {
            ...summary(),
            top_categories: [{ name: 'Water', count: 12 }, { name: 'Roads', count: 5 }],
            top_locations: [{ name: 'Bailhongal segment', count: 9 }],
            window: { kind: 'days', from: '2026-10-19', to: '2026-11-17', days: 30 },
            bucket_days: 7,
            trend: Array.from({ length: 8 }, (_, i) => ({ period_start: `2026-11-0${1 + i}`, period_end: `2026-11-${10 + i}`, received: i, resolved: Math.floor(i / 2) })),
        },
    };
    beforeEach(() => {
        apiMocks.partnerClientSummary.mockResolvedValue(detail);
        apiMocks.partnerClientOverview.mockResolvedValue(overviewPayload());
    });

    it('opens on the Overview with work waiting on the office, counted once', async () => {
        render(<PartnerClientPage />);
        const attention = await screen.findByRole('region', { name: /requires attention/i });
        expect(within(attention).getByTestId('attention-needs_review')).toHaveTextContent('4');
        expect(within(attention).getByTestId('attention-unassigned')).toHaveTextContent('13');
        expect(within(attention).getByTestId('attention-needs_location')).toHaveTextContent('2');
        // sync issues and ready-to-file live in government tracking only
        expect(within(attention).queryByText(/sync|ready to file/i)).toBeNull();
        const updates = screen.getByRole('region', { name: /updates and office workload/i });
        expect(within(updates).getByText('Government updates received').nextSibling).toHaveTextContent('3');
        expect(within(updates).getByText('New letters awaiting intake').nextSibling).toHaveTextContent('5');
        expect(apiMocks.partnerClientOverview).toHaveBeenCalledWith('7');
    });

    it('shows government tracking as a pipeline, outcomes and health, separate from Needle resolution', async () => {
        render(<PartnerClientPage />);
        const govt = await screen.findByRole('region', { name: /government grievance tracking/i });
        for (const label of ['Ready to file', 'Submitted', 'Registered', 'Forwarded', 'Awaiting action', 'Resolved', 'Disposed', 'Rejected', 'Awaiting verification', 'Portal sync issues']) {
            expect(within(govt).getByText(label)).toBeInTheDocument();
        }
        expect(within(govt).getByTestId('govt-awaiting_action')).toHaveTextContent('8');
        expect(within(govt).getByTestId('govt-awaiting_verification')).toHaveTextContent('9');
        expect(within(govt).getByText(/separate from needle.s own resolution/i)).toBeInTheDocument();
        expect(screen.getByText('Bailhongal')).toBeInTheDocument();
        expect(screen.getByText('Water supply')).toBeInTheDocument();
    });

    it('never shows a grievance list or the analytics charts on the Overview', async () => {
        render(<PartnerClientPage />);
        await screen.findByRole('region', { name: /government grievance tracking/i });
        expect(screen.queryByRole('table')).toBeNull();
        expect(screen.queryByRole('img', { name: /grievances by week/i })).toBeNull();
    });

    it('renders headline numbers, rankings and accessible charts on Analytics', async () => {
        render(<PartnerClientPage />);
        await openTab('Analytics');
        expect(screen.getAllByText('75%').length).toBeGreaterThan(0);
        expect(screen.getByText('2.4d')).toBeInTheDocument();
        expect(screen.getByText('Water')).toBeInTheDocument();
        expect(screen.getByRole('img', { name: /grievances by week/i })).toBeInTheDocument();
        expect(screen.getByRole('img', { name: /resolution rate by week/i })).toBeInTheDocument();
        expect(screen.queryByRole('region', { name: /government grievance tracking/i })).toBeNull();
        expect(apiMocks.partnerClientSummary).toHaveBeenCalledWith('7', { kind: 'days', days: 30 });
    });

    it('compares the client with the portfolio from aggregate figures', async () => {
        render(<PartnerClientPage />);
        await openTab('Analytics');
        const cmp = await screen.findByRole('region', { name: /against your portfolio/i });
        expect(within(cmp).getByText('Resolution rate')).toBeInTheDocument();
        expect(within(cmp).getByText('portfolio 69%')).toBeInTheDocument();
    });

    it('refetches the client when the Analytics period changes', async () => {
        render(<PartnerClientPage />);
        await openTab('Analytics');
        fireEvent.click(screen.getByRole('button', { name: '90 days' }));
        await waitFor(() => expect(apiMocks.partnerClientSummary).toHaveBeenLastCalledWith('7', { kind: 'days', days: 90 }));
    });

    it('shows the report only inside a fully sandboxed iframe', async () => {
        apiMocks.partnerClientReport.mockResolvedValue('<html><body>Report body</body></html>');
        render(<PartnerClientPage />);
        await openTab('Reports');

        fireEvent.click(screen.getByRole('button', { name: /generate report/i }));
        const frame = await screen.findByTitle(/report preview/i);
        expect(frame).toHaveAttribute('sandbox', '');
        expect(frame.getAttribute('srcdoc')).toContain('Report body');
        expect(screen.getByRole('button', { name: /open to print/i })).toBeInTheDocument();
    });

    it('drops a generated report when the period changes', async () => {
        apiMocks.partnerClientReport.mockResolvedValue('<html>30d</html>');
        render(<PartnerClientPage />);
        await openTab('Reports');
        fireEvent.click(screen.getByRole('button', { name: /generate report/i }));
        await screen.findByTitle(/report preview/i);

        fireEvent.click(screen.getByRole('button', { name: '7 days' }));
        await waitFor(() => expect(screen.queryByTitle(/report preview/i)).toBeNull());
        expect(screen.getByRole('button', { name: /generate report/i })).toBeInTheDocument();
    });

    it('switches between clients and does not link paused ones', async () => {
        render(<PartnerClientPage />);
        await screen.findByRole('heading', { name: 'Asha Patil', level: 1 });
        fireEvent.click(screen.getByRole('button', { name: /switch client/i }));
        const dialog = await screen.findByRole('dialog', { name: /switch client/i });
        expect(await within(dialog).findByRole('link', { name: /ravi kulkarni/i })).toHaveAttribute('href', '/partner/dashboard/clients/8');
        expect(within(dialog).queryByRole('link', { name: /old client/i })).toBeNull();
        fireEvent.change(within(dialog).getByLabelText('Find a client'), { target: { value: 'ravi' } });
        expect(within(dialog).queryByRole('link', { name: /asha patil/i })).toBeNull();
    });

    it('shows an unavailable state, not zeros, when the overview fails, and retries', async () => {
        apiMocks.partnerClientOverview.mockReset();
        apiMocks.partnerClientOverview.mockRejectedValueOnce(new Error('boom')).mockResolvedValue(overviewPayload());
        render(<PartnerClientPage />);
        expect(await screen.findByRole('alert')).toHaveTextContent(/overview is unavailable/i);
        expect(screen.queryByRole('region', { name: /government grievance tracking/i })).toBeNull();
        fireEvent.click(screen.getByRole('button', { name: /retry/i }));
        expect(await screen.findByRole('region', { name: /government grievance tracking/i })).toBeInTheDocument();
    });

    it('sends the partner to sign-in when the overview call returns 401', async () => {
        apiMocks.partnerClientOverview.mockReset();
        apiMocks.partnerClientOverview.mockRejectedValue(Object.assign(new Error('expired'), { status: 401 }));
        render(<PartnerClientPage />);
        await waitFor(() => expect(replaceMock).toHaveBeenCalledWith('/partner'));
    });

    it('explains an unavailable client instead of showing blanks', async () => {
        apiMocks.partnerClientSummary.mockReset();
        apiMocks.partnerClientSummary.mockRejectedValue(Object.assign(new Error('Client not found'), { status: 404 }));
        render(<PartnerClientPage />);
        expect(await screen.findByRole('alert')).toHaveTextContent(/isn.t available/i);
        expect(screen.getByRole('alert')).toHaveTextContent('Client not found');
    });
});

describe('partner sign-in page', () => {
    it('signs in and goes to the dashboard', async () => {
        const signIn = vi.fn().mockResolvedValue({ must_change_password: false });
        sessionState.current = { ready: true, token: null, mustChangePassword: false, signIn, changePassword: vi.fn() };
        render(<PartnerLoginPage />);

        fireEvent.change(screen.getByLabelText('Work email'), { target: { value: 'ops@firm.in' } });
        fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Secret123' } });
        fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

        await waitFor(() => expect(signIn).toHaveBeenCalledWith('ops@firm.in', 'Secret123'));
        await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/partner/dashboard'));
    });

    it('shows the server message on a failed sign-in', async () => {
        const signIn = vi.fn().mockRejectedValue(new Error('Invalid credentials'));
        sessionState.current = { ready: true, token: null, mustChangePassword: false, signIn, changePassword: vi.fn() };
        render(<PartnerLoginPage />);
        fireEvent.change(screen.getByLabelText('Work email'), { target: { value: 'ops@firm.in' } });
        fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'bad' } });
        fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
        expect(await screen.findByRole('alert')).toHaveTextContent('Invalid credentials');
        expect(pushMock).not.toHaveBeenCalled();
    });

    it('forces a password change with a matching confirmation before continuing', async () => {
        const changePassword = vi.fn().mockResolvedValue({});
        sessionState.current = { ready: true, token: 'tok', mustChangePassword: true, signIn: vi.fn(), changePassword };
        render(<PartnerLoginPage />);

        expect(screen.getByRole('heading', { name: /choose a new password/i })).toBeInTheDocument();
        fireEvent.change(screen.getByLabelText('Temporary password'), { target: { value: 'Temp12345' } });
        fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'NewSecret9' } });
        fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'Different9' } });
        fireEvent.click(screen.getByRole('button', { name: /set password/i }));
        expect(await screen.findByRole('alert')).toHaveTextContent(/do not match/i);
        expect(changePassword).not.toHaveBeenCalled();

        fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'NewSecret9' } });
        fireEvent.click(screen.getByRole('button', { name: /set password/i }));
        await waitFor(() => expect(changePassword).toHaveBeenCalledWith('Temp12345', 'NewSecret9'));
        await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/partner/dashboard'));
    });

    it('skips the form and redirects when already signed in', async () => {
        signedIn();
        render(<PartnerLoginPage />);
        await waitFor(() => expect(replaceMock).toHaveBeenCalledWith('/partner/dashboard'));
    });
});
