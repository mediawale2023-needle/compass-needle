import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock, apiPostMock, pushMock, authState } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
    apiPostMock: vi.fn(),
    pushMock: vi.fn(),
    authState: { user: { username: 'boss', role: 'sysadmin' } },
}));

vi.mock('@/lib/api', () => ({
    apiGet: (path) => apiGetMock(path),
    apiPost: (path, body) => apiPostMock(path, body),
}));
vi.mock('@/lib/auth', () => ({ useAuth: () => ({ user: authState.user }) }));
const stableRouter = { push: pushMock };
vi.mock('next/navigation', () => ({ useRouter: () => stableRouter, usePathname: () => '/dashboard/accounts/new' }));
vi.mock('next/link', () => ({ default: ({ href, children, ...p }) => <a href={typeof href === 'string' ? href : '#'} {...p}>{children}</a> }));

import CreateAccountPage from '@/components/admin-domains/accounts/CreateAccountPage';
import AcquisitionPanel from '@/components/admin-domains/partners/AcquisitionPanel';

const ACTIVE = [{ id: 3, name: 'Rajdhani Strategy' }, { id: 5, name: 'Bravo Campaigns' }];

function mockGets(over = {}) {
    apiGetMock.mockImplementation(async (path) => {
        if (over[path]) return over[path]();
        if (path === '/api/admin/constituencies') return { constituencies: [] };
        if (path === '/api/admin/partners/selectable') return { partners: ACTIVE };
        throw new Error(`unexpected GET ${path}`);
    });
}

beforeEach(() => {
    [apiGetMock, apiPostMock, pushMock].forEach((m) => m.mockReset());
    authState.user = { username: 'boss', role: 'sysadmin' };
});

// Walk the 4-stage onboarding form with the minimum valid input.
const field = (label) => screen.getByLabelText(label, { exact: false });
function fillIdentity() {
    fireEvent.change(field('MP full name'), { target: { value: 'Asha Patil' } });
    fireEvent.change(field('State'), { target: { value: 'Karnataka' } });
}
const next = (to) => fireEvent.click(screen.getByRole('button', { name: new RegExp(`Continue to ${to}`) }));
const pickChannel = (name) => fireEvent.click(screen.getByRole('radio', { name }));
const partnerSelect = () => screen.findByRole('combobox', { name: /^partner/i });
const create = () => fireEvent.click(screen.getByRole('button', { name: 'Create account and continue setup' }));
async function reachReview() {
    fillIdentity(); next('Seat & Access');
    fireEvent.change(field('Username'), { target: { value: 'asha' } });
    fireEvent.change(field('Temporary password'), { target: { value: 'TempPass1!' } });
    next('Configure'); next('Review & Create');
    await screen.findByRole('heading', { name: 'Review & Create' });
}

describe('onboarding: acquisition source', () => {
    it('defaults to Direct, with no partner picker, and sends no partner', async () => {
        mockGets();
        apiPostMock.mockResolvedValue({ success: true, tenant_id: 41 });
        render(<CreateAccountPage />);

        expect(screen.getByRole('radio', { name: /Direct — Needle/ })).toBeChecked();
        expect(screen.getByRole('radio', { name: /Partner \/ Consultancy/ })).not.toBeChecked();
        expect(screen.queryByRole('combobox', { name: /^partner/i })).toBeNull();
        expect(apiGetMock).not.toHaveBeenCalledWith('/api/admin/partners/selectable');   // no needless fetch

        await reachReview();
        expect(within(screen.getByRole('region', { name: 'Identity' })).getByText('Direct — Needle')).toBeInTheDocument();
        create();
        await waitFor(() => expect(apiPostMock).toHaveBeenCalledTimes(1));
        const [path, body] = apiPostMock.mock.calls[0];
        expect(path).toBe('/api/admin/mps');
        expect(body.acquisition_channel).toBe('direct');
        expect(body).not.toHaveProperty('partner_id');
    });

    it('shows a dropdown of the active partners the server offers when Partner is chosen', async () => {
        mockGets();
        render(<CreateAccountPage />);
        pickChannel(/Partner \/ Consultancy/);

        const select = await partnerSelect();
        expect(apiGetMock).toHaveBeenCalledWith('/api/admin/partners/selectable');          // server-filtered list, never the full list
        expect(apiGetMock).not.toHaveBeenCalledWith('/api/admin/partners');
        expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['— select partner —', 'Rajdhani Strategy', 'Bravo Campaigns']);
    });

    it('requires a partner before the form can continue', async () => {
        mockGets();
        render(<CreateAccountPage />);
        pickChannel(/Partner \/ Consultancy/);
        await partnerSelect();
        fillIdentity(); next('Seat & Access');

        expect(screen.getByText(/select the partner that brought this tenant/i)).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Identity' })).toBeInTheDocument();   // did not advance
        expect(apiPostMock).not.toHaveBeenCalled();
    });

    it('submits the chosen partner, shows it in the review, and needs no seat request', async () => {
        vi.useRealTimers();
        mockGets();
        apiPostMock.mockResolvedValue({ success: true, tenant_id: 41, acquisition: { channel: 'partner', partner_id: 3 } });
        render(<CreateAccountPage />);
        pickChannel(/Partner \/ Consultancy/);
        fireEvent.change(await partnerSelect(), { target: { value: '3' } });
        await reachReview();

        expect(within(screen.getByRole('region', { name: 'Identity' })).getByText('Partner — Rajdhani Strategy')).toBeInTheDocument();   // visible before submission
        create();
        await waitFor(() => expect(apiPostMock).toHaveBeenCalledTimes(1));
        const [path, body] = apiPostMock.mock.calls[0];
        expect(path).toBe('/api/admin/mps');
        expect(body).toMatchObject({ acquisition_channel: 'partner', partner_id: 3 });
        expect(await screen.findByText(/attributed to rajdhani strategy/i)).toBeInTheDocument();
        expect(apiPostMock.mock.calls.some(([p]) => /seat/.test(p))).toBe(false);
    });

    it('switching back to Direct drops the selected partner', async () => {
        mockGets();
        apiPostMock.mockResolvedValue({ success: true, tenant_id: 41 });
        render(<CreateAccountPage />);
        pickChannel(/Partner \/ Consultancy/);
        fireEvent.change(await partnerSelect(), { target: { value: '5' } });
        pickChannel(/Direct — Needle/);
        await reachReview();
        create();
        await waitFor(() => expect(apiPostMock).toHaveBeenCalled());
        expect(apiPostMock.mock.calls[0][1]).toMatchObject({ acquisition_channel: 'direct' });
        expect(apiPostMock.mock.calls[0][1]).not.toHaveProperty('partner_id');
    });

    it('shows the server error (for example an inactive partner) and does not redirect', async () => {
        mockGets();
        apiPostMock.mockRejectedValue(new Error('Selected partner is inactive and cannot receive new tenants.'));
        render(<CreateAccountPage />);
        pickChannel(/Partner \/ Consultancy/);
        fireEvent.change(await partnerSelect(), { target: { value: '3' } });
        await reachReview();
        create();
        expect(await screen.findByText(/partner is inactive/i)).toBeInTheDocument();
        expect(pushMock).not.toHaveBeenCalled();
    });

    it('blocks partner onboarding when the partner list cannot be loaded, and recovers on retry', async () => {
        mockGets({ '/api/admin/partners/selectable': async () => { throw new Error('down'); } });
        render(<CreateAccountPage />);
        pickChannel(/Partner \/ Consultancy/);
        expect(await screen.findByText(/partner list unavailable/i)).toBeInTheDocument();
        fillIdentity(); next('Seat & Access');
        expect(screen.getByRole('heading', { name: 'Identity' })).toBeInTheDocument();    // still on stage 1

        mockGets();
        fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
        expect(await partnerSelect()).toBeInTheDocument();
    });

    it('says so when there are no active partners', async () => {
        mockGets({ '/api/admin/partners/selectable': async () => ({ partners: [] }) });
        render(<CreateAccountPage />);
        pickChannel(/Partner \/ Consultancy/);
        expect(await screen.findByText(/no active partners/i)).toBeInTheDocument();
    });
});

describe('Account 360: acquisition card', () => {
    const partnerAcq = { recorded: true, channel: 'partner', partner_id: 3, partner_name: 'Rajdhani Strategy', attributed_at: '2026-11-10T09:00:00', attributed_by: 'sanket', access_status: 'active' };

    it('shows channel, partner, date, attributing staff member and access state', () => {
        render(<AcquisitionPanel tenantId="41" acquisition={partnerAcq} history={[]} />);
        expect(screen.getByText('Partner — Rajdhani Strategy')).toBeInTheDocument();
        expect(screen.getByText('sanket')).toBeInTheDocument();
        expect(screen.getByText('10 Nov 2026')).toBeInTheDocument();
        expect(screen.getByText('Live')).toBeInTheDocument();
    });

    it('shows a paused association without changing the attribution', () => {
        render(<AcquisitionPanel tenantId="41" acquisition={{ ...partnerAcq, access_status: 'paused' }} history={[]} />);
        expect(screen.getByText('Partner — Rajdhani Strategy')).toBeInTheDocument();
        expect(screen.getByText('Paused')).toBeInTheDocument();
    });

    it('shows direct tenants, including accounts that predate tracking', () => {
        const { rerender } = render(<AcquisitionPanel tenantId="41" acquisition={{ recorded: true, channel: 'direct', attributed_at: '2026-11-10T09:00:00', attributed_by: 'sanket' }} history={[]} />);
        expect(screen.getByText('Direct — Needle')).toBeInTheDocument();
        rerender(<AcquisitionPanel tenantId="41" acquisition={{ recorded: false, channel: 'direct' }} history={[]} />);
        expect(screen.getByText(/created before acquisition tracking/i)).toBeInTheDocument();
    });

    it('says unavailable, not "Direct", when the lookup failed', () => {
        render(<AcquisitionPanel tenantId="41" acquisition={null} history={[]} />);
        expect(screen.getByRole('status')).toHaveTextContent(/unavailable/i);
        expect(screen.queryByText(/direct — needle/i)).toBeNull();
    });

    it('offers attribution changes to super admins only', () => {
        authState.user = { username: 'plain', role: 'admin' };
        const { unmount } = render(<AcquisitionPanel tenantId="41" acquisition={partnerAcq} history={[]} />);
        expect(screen.queryByRole('button', { name: /change attribution/i })).toBeNull();
        unmount();
        authState.user = { username: 'boss', role: 'super_admin' };
        render(<AcquisitionPanel tenantId="41" acquisition={partnerAcq} history={[]} />);
        expect(screen.getByRole('button', { name: /change attribution/i })).toBeInTheDocument();
    });

    it('requires a target and a reason, excludes the current partner, then posts the change', async () => {
        mockGets();
        apiPostMock.mockResolvedValue({ success: true });
        const onChanged = vi.fn();
        render(<AcquisitionPanel tenantId="41" acquisition={partnerAcq} history={[]} onChanged={onChanged} />);
        fireEvent.click(screen.getByRole('button', { name: /change attribution/i }));

        const select = await screen.findByLabelText(/new acquisition source/i);
        expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['— select —', 'Direct — Needle', 'Partner — Bravo Campaigns']);
        const confirm = screen.getAllByRole('button', { name: 'Change attribution' }).pop();
        expect(confirm).toBeDisabled();
        fireEvent.change(select, { target: { value: '5' } });
        expect(confirm).toBeDisabled();                                   // still no reason
        fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: 'ok' } });
        expect(confirm).toBeDisabled();                                   // too short
        fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: 'Brought in by Bravo, mislabelled' } });
        expect(confirm).toBeEnabled();
        fireEvent.click(confirm);

        await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith('/api/admin/partners/tenants/41/attribution/reassign', {
            partner_id: 5, reason: 'Brought in by Bravo, mislabelled',
        }));
        await waitFor(() => expect(onChanged).toHaveBeenCalled());
    });

    it('moving to Direct sends a null partner and surfaces server refusals', async () => {
        mockGets();
        apiPostMock.mockRejectedValue(new Error('Super-admin access required for this action.'));
        render(<AcquisitionPanel tenantId="41" acquisition={partnerAcq} history={[]} />);
        fireEvent.click(screen.getByRole('button', { name: /change attribution/i }));
        fireEvent.change(await screen.findByLabelText(/new acquisition source/i), { target: { value: 'direct' } });
        fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: 'Customer left the consultancy' } });
        fireEvent.click(screen.getAllByRole('button', { name: 'Change attribution' }).pop());
        expect(await screen.findByRole('alert')).toHaveTextContent(/super-admin access required/i);
        expect(apiPostMock).toHaveBeenCalledWith('/api/admin/partners/tenants/41/attribution/reassign', { partner_id: null, reason: 'Customer left the consultancy' });
    });

    it('lists past attribution changes with who, when and why', () => {
        const history = [{ id: 2, event: 'reassigned', from_channel: 'partner', from_partner_id: 3, to_channel: 'direct', to_partner_id: null, reason: 'Left the consultancy', changed_by: 'sanket', created_at: '2026-11-12T09:00:00' },
            { id: 1, event: 'onboarded', from_channel: null, to_channel: 'partner', to_partner_id: 3, reason: null, changed_by: 'sanket', created_at: '2026-11-10T09:00:00' }];
        render(<AcquisitionPanel tenantId="41" acquisition={partnerAcq} history={history} />);
        expect(screen.getByText(/left the consultancy/i)).toBeInTheDocument();
        expect(screen.getByText(/partner #3 → direct/i)).toBeInTheDocument();
    });
});
