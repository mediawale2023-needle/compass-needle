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
        partnerClientBriefing: vi.fn(),
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

const trend = (n) => Array.from({ length: 5 }, (_, i) => (i === 4 ? n : 0));
const briefingPayload = (over = {}) => ({
    client: { id: 7, client_label: 'Asha Patil' },
    briefing: {
        window: { kind: 'days', from: '2026-10-25', to: '2026-11-24', days: 30 },
        compare: { from: '2026-09-25', to: '2026-10-24' },
        bucket_days: 7,
        periods: Array.from({ length: 5 }, (_, i) => ({ period_start: `2026-10-${20 + i}`, period_end: `2026-10-${21 + i}` })),
        momentum: {
            received: { now: 146, previous: 124, trend: trend(146) },
            filed: { now: 12, previous: 31, trend: trend(12) },
            resolved_by_government: { now: 9, previous: 7, trend: trend(9) },
            other_actions: { now: 38, previous: 35, trend: trend(38) },
            pending: { now: 96, previous: 71, trend: trend(96) },
        },
        funnel: { received: 146, action_taken: 50, filed: 12, resolved_by_government: 9, pending: 96, ready_to_file: 9, oldest_ready_days: 16 },
        issues: [
            { name: 'Roads & bridges', count: 64, previous: 44, trend: trend(64), top_localities: [{ name: 'Shahpur', count: 19 }, { name: 'Tilakwadi', count: 14 }] },
            { name: 'Water supply', count: 31, previous: 33, trend: trend(31), top_localities: [{ name: 'Tilakwadi', count: 9 }, { name: 'Camp', count: 7 }] },
            { name: 'Drainage & sewage', count: 22, previous: 11, trend: trend(22), top_localities: [{ name: 'Shahpur', count: 9 }, { name: 'Anagol', count: 6 }] },
            { name: 'Electricity', count: 14, previous: 16, trend: trend(14), top_localities: [{ name: 'Camp', count: 5 }] },
            { name: 'Land & revenue', count: 6, previous: 9, trend: trend(6), top_localities: [] },
        ],
        hotspots: {
            columns: ['Roads & bridges', 'Water supply', 'Drainage & sewage', 'Electricity'],
            localities: Array.from({ length: 9 }, (_, i) => ({
                name: ['Shahpur', 'Tilakwadi', 'Anagol', 'Camp', 'Vadgaon', 'Hindwadi', 'Khasbag', 'Bhagya Nagar', 'Shastri Nagar'][i],
                total: 30 - i * 3, counts: [10 - i, 8 - i, 6 - Math.min(i, 6), 6 - Math.min(i, 6)],
            })),
            total_localities: 9, unmapped: 4,
        },
        wins: [{ name: 'Water supply', count: 5, localities: ['Tilakwadi', 'Camp'] }, { name: 'Electricity', count: 3, localities: ['Anagol'] }, { name: 'Pensions', count: 1, localities: [] }],
        wins_total: 9,
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
        apiMocks.partnerClientBriefing.mockResolvedValue(briefingPayload());
    });

    it('opens on the Briefing with an issue-only headline and the wins beside it', async () => {
        render(<PartnerClientPage />);
        const brief = await screen.findByRole('region', { name: 'Briefing' });
        expect(within(brief).getByText(/roads & bridges accounts for 44% of complaints, and/i)).toBeInTheDocument();
        expect(within(brief).getByText(/drainage & sewage complaints doubled in shahpur and anagol/i)).toBeInTheDocument();
        expect(within(brief).getByText(/biggest issue: 64 complaints, up 45%/i)).toBeInTheDocument();
        expect(within(brief).getByText(/water supply remains a steady concern/i)).toBeInTheDocument();
        expect(within(brief).getByText(/electricity and land & revenue complaints eased/i)).toBeInTheDocument();
        // the prose is about issues only: no delivery figures
        expect(within(brief).queryByText(/pending|filed with government/i)).toBeNull();
        expect(within(brief).getByText('Wins to publicise')).toBeInTheDocument();
        expect(within(brief).getByText('Tilakwadi and Camp')).toBeInTheDocument();
        expect(within(brief).queryByText(/ready-to-use/i)).toBeNull();
        expect(apiMocks.partnerClientBriefing).toHaveBeenCalledWith('7', { kind: 'days', days: 30 });
    });

    it('shows five momentum cards with the change on the previous period', async () => {
        render(<PartnerClientPage />);
        const mom = await screen.findByRole('region', { name: 'Momentum' });
        for (const [label, value] of [['Complaints received', '146'], ['Filed with government', '12'], ['Resolved by government', '9'], ['Other actions taken', '38'], ['Pending', '96']]) {
            const card = within(mom).getByText(label).closest('.pd-kpi');
            expect(card).toHaveTextContent(value);
        }
        expect(within(mom).getByText('↓ 61%')).toHaveClass('bad');   // fewer filings is bad
        expect(within(mom).getByText('↑ 35%')).toHaveClass('bad');   // more pending is bad
        expect(within(mom).getByText('↑ 29%')).toHaveClass('good');  // more resolved is good
    });

    it('lists localities by name, top six first, with see-all and search', async () => {
        render(<PartnerClientPage />);
        const hot = await screen.findByRole('region', { name: 'Hotspots' });
        expect(within(hot).getByText('Shahpur')).toBeInTheDocument();
        expect(within(hot).queryByText('Bhagya Nagar')).toBeNull();
        expect(within(hot).queryByText(/ward/i)).toBeNull();
        fireEvent.click(within(hot).getByRole('button', { name: /see all 9 localities/i }));
        expect(within(hot).getByText('Bhagya Nagar')).toBeInTheDocument();
        fireEvent.change(within(hot).getByLabelText('Search localities'), { target: { value: 'nagar' } });
        expect(within(hot).queryByText('Shahpur')).toBeNull();
        expect(within(hot).getByText('2 shown')).toBeInTheDocument();
        fireEvent.click(within(hot).getByRole('button', { name: /show top 6/i }));
        expect(within(hot).queryByText('Bhagya Nagar')).toBeNull();
    });

    it('shows the delivery funnel with the filing callout and no office-execution panel', async () => {
        render(<PartnerClientPage />);
        const del = await screen.findByRole('region', { name: /from complaint to government action/i });
        expect(within(del).getByText('Action taken').nextSibling.nextSibling).toHaveTextContent('50');
        expect(within(del).getByText(/the drop is at filing/i)).toBeInTheDocument();
        expect(within(del).getByText(/9 grievances are prepared for filing/i)).toBeInTheDocument();
        expect(screen.queryByText(/office execution/i)).toBeNull();
        expect(screen.queryByText(/where things stand/i)).toBeNull();
    });

    it('refetches the briefing when the period changes', async () => {
        render(<PartnerClientPage />);
        await screen.findByRole('region', { name: 'Briefing' });
        fireEvent.click(screen.getByRole('button', { name: '90 days' }));
        await waitFor(() => expect(apiMocks.partnerClientBriefing).toHaveBeenLastCalledWith('7', { kind: 'days', days: 90 }));
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

    it('shows an unavailable state, not zeros, when the briefing fails, and retries', async () => {
        apiMocks.partnerClientBriefing.mockReset();
        apiMocks.partnerClientBriefing.mockRejectedValueOnce(new Error('boom')).mockResolvedValue(briefingPayload());
        render(<PartnerClientPage />);
        expect(await screen.findByRole('alert')).toHaveTextContent(/briefing is unavailable/i);
        expect(screen.queryByRole('region', { name: 'Momentum' })).toBeNull();
        fireEvent.click(screen.getByRole('button', { name: /retry/i }));
        expect(await screen.findByRole('region', { name: 'Momentum' })).toBeInTheDocument();
    });

    it('sends the partner to sign-in when the briefing call returns 401', async () => {
        apiMocks.partnerClientBriefing.mockReset();
        apiMocks.partnerClientBriefing.mockRejectedValue(Object.assign(new Error('expired'), { status: 401 }));
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
