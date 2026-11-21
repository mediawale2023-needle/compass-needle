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

const summary = (over = {}) => ({
    total: 40, resolved: 30, open: 10, critical: 3, resolution_rate: 0.75, avg_resolution_days: 2.4, ...over,
});

const clientsPayload = (over = {}) => ({
    days: 30, active_clients: 2,
    portfolio: { total: 40, resolved: 30, open: 10, critical: 3 },
    clients: [
        { id: 7, client_label: 'Asha Patil', constituency: 'Belagavi South', seat_type: 'mla', status: 'active', summary: summary() },
        { id: 8, client_label: 'Ravi Kulkarni', constituency: 'Pune Cantonment', seat_type: 'mla', status: 'active', summary: summary({ total: 12, resolved: 6, open: 6, critical: 0 }) },
        { id: 9, client_label: 'Old Client', constituency: '', seat_type: 'mp', status: 'paused', summary: null },
    ],
    ...over,
});

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
    replaceMock.mockReset();
    pushMock.mockReset();
    signedIn();
});

describe('partner portfolio page', () => {
    it('shows portfolio totals and one row per client with the right status', async () => {
        apiMocks.partnerClients.mockResolvedValue(clientsPayload());
        render(<PartnerDashboardPage />);

        expect(await screen.findByText('Asha Patil')).toBeInTheDocument();
        expect(screen.getByText('2 active clients')).toBeInTheDocument();
        expect(screen.getAllByText('Live')).toHaveLength(2);
        expect(screen.getByText('Paused')).toBeInTheDocument();

        // Only live clients are clickable; a paused client grants no access
        expect(screen.getByRole('link', { name: /open asha patil/i })).toHaveAttribute('href', '/partner/dashboard/clients/7');
        expect(screen.getByRole('link', { name: /open ravi kulkarni/i })).toHaveAttribute('href', '/partner/dashboard/clients/8');
        expect(screen.queryByRole('link', { name: /open old client/i })).toBeNull();

        const section = screen.getByRole('region', { name: /portfolio totals/i });
        expect(within(section).getByText('40')).toBeInTheDocument();
    });

    it('refetches when the period changes', async () => {
        apiMocks.partnerClients.mockResolvedValue(clientsPayload());
        render(<PartnerDashboardPage />);
        await screen.findByText('Asha Patil');

        fireEvent.click(screen.getByRole('button', { name: '90 days' }));
        await waitFor(() => expect(apiMocks.partnerClients).toHaveBeenLastCalledWith(90));
    });

    it('shows an unavailable state, not zeros, when the API fails, and retries', async () => {
        apiMocks.partnerClients.mockRejectedValueOnce(Object.assign(new Error('Could not reach the server.'), { status: 0 }));
        render(<PartnerDashboardPage />);

        expect(await screen.findByRole('alert')).toHaveTextContent(/unavailable right now/i);
        expect(screen.queryByRole('region', { name: /portfolio totals/i })).toBeNull();

        apiMocks.partnerClients.mockResolvedValueOnce(clientsPayload());
        fireEvent.click(screen.getByRole('button', { name: /retry/i }));
        expect(await screen.findByText('Asha Patil')).toBeInTheDocument();
    });

    it('distinguishes an empty portfolio from a failed load', async () => {
        apiMocks.partnerClients.mockResolvedValue(clientsPayload({
            active_clients: 0, clients: [], portfolio: { total: 0, resolved: 0, open: 0, critical: 0 },
        }));
        render(<PartnerDashboardPage />);
        expect(await screen.findByText('No clients yet')).toBeInTheDocument();
        expect(screen.queryByText(/unavailable/i)).toBeNull();
    });

    it('has no seat-request form, seat-cap indicator or cap warning', async () => {
        apiMocks.partnerClients.mockResolvedValue(clientsPayload());
        render(<PartnerDashboardPage />);
        await screen.findByText('Asha Patil');
        expect(screen.queryByRole('button', { name: /request client seat/i })).toBeNull();
        expect(screen.queryByText(/seat cap|seats used|awaiting activation|raise/i)).toBeNull();
    });

    it('lists any number of attributed clients without limiting or warning', async () => {
        const many = Array.from({ length: 40 }, (_, i) => ({
            id: 100 + i, client_label: `Client ${i}`, constituency: 'X', seat_type: 'mla', status: 'active', summary: summary(),
        }));
        apiMocks.partnerClients.mockResolvedValue(clientsPayload({ active_clients: 40, clients: many }));
        render(<PartnerDashboardPage />);
        expect(await screen.findByText('40 active clients')).toBeInTheDocument();
        expect(screen.getAllByRole('link', { name: /^open client/i })).toHaveLength(40);
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
            top_locations: [{ name: 'Ward 5', count: 9 }],
            weekly: Array.from({ length: 8 }, (_, i) => ({ week_ending: `2026-11-${10 + i}`, received: i, resolved: Math.floor(i / 2) })),
        },
    };

    it('renders headline numbers, rankings and an accessible weekly chart', async () => {
        apiMocks.partnerClientSummary.mockResolvedValue(detail);
        render(<PartnerClientPage />);

        expect(await screen.findByRole('heading', { name: 'Asha Patil' })).toBeInTheDocument();
        expect(screen.getByText('75%')).toBeInTheDocument();
        expect(screen.getByText('2.4d')).toBeInTheDocument();
        expect(screen.getByText('Water')).toBeInTheDocument();
        expect(screen.getByRole('img', { name: /weekly grievances/i })).toBeInTheDocument();
        expect(apiMocks.partnerClientSummary).toHaveBeenCalledWith('7', 30);
    });

    it('shows the report only inside a fully sandboxed iframe', async () => {
        apiMocks.partnerClientSummary.mockResolvedValue(detail);
        apiMocks.partnerClientReport.mockResolvedValue('<html><body>Report body</body></html>');
        render(<PartnerClientPage />);
        await screen.findByRole('heading', { name: 'Asha Patil' });

        fireEvent.click(screen.getByRole('button', { name: /generate report/i }));
        const frame = await screen.findByTitle(/report preview/i);
        expect(frame).toHaveAttribute('sandbox', '');
        expect(frame.getAttribute('srcdoc')).toContain('Report body');
        expect(screen.getByRole('button', { name: /open to print/i })).toBeInTheDocument();
    });

    it('drops a generated report when the period changes', async () => {
        apiMocks.partnerClientSummary.mockResolvedValue(detail);
        apiMocks.partnerClientReport.mockResolvedValue('<html>30d</html>');
        render(<PartnerClientPage />);
        await screen.findByRole('heading', { name: 'Asha Patil' });
        fireEvent.click(screen.getByRole('button', { name: /generate report/i }));
        await screen.findByTitle(/report preview/i);

        fireEvent.click(screen.getByRole('button', { name: '7 days' }));
        await waitFor(() => expect(screen.queryByTitle(/report preview/i)).toBeNull());
        expect(screen.getByRole('button', { name: /generate report/i })).toBeInTheDocument();
    });

    it('explains an unavailable client instead of showing blanks', async () => {
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
