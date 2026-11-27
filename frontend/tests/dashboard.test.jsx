import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock, apiPostMock, pushMock } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
    apiPostMock: vi.fn(),
    pushMock: vi.fn(),
}));

vi.mock('@/lib/auth', () => ({
    useAuth: () => ({
        user: {
            role: 'mp',
            display_name: 'Arun Kumar',
        },
    }),
}));

vi.mock('@/lib/api', () => ({
    apiGet: (path) => apiGetMock(path),
    apiPost: (path, body) => apiPostMock(path, body),
}));

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: pushMock,
    }),
}));

vi.mock('next/link', () => ({
    default: ({ href, children, ...props }) => (
        <a href={typeof href === 'string' ? href : '#'} {...props}>
            {children}
        </a>
    ),
}));

import DashboardPage from '@/app/dashboard/page';

const OVERVIEW = {
    seat: 'Belagavi South',
    date_label: 'Today',
    attention_counts: [
        { key: 'needs_review', label: 'Needs review', value: 3, tone: 'red' },
        { key: 'needs_location', label: 'Needs location', value: 1, tone: 'amber' },
        { key: 'sync_issues', label: 'Sync issues', value: 1, tone: 'rust' },
        { key: 'govt_updates', label: 'Govt updates', value: 2, tone: 'green' },
        { key: 'ready_to_file', label: 'Ready to file', value: 4, tone: 'green' },
    ],
    attention_queue: [
        {
            id: 101,
            case_ref: '#CN-101',
            thread_count: 2,
            channel: 'WhatsApp',
            meta: 'Thread · 2 complaints · 1h',
            message: 'Pipeline burst in Whitefield since morning',
            issue: 'Water supply',
            location: 'Whitefield · Ward 5',
            state: 'Needs Review',
            needle_status: 'Pending Review',
            govt_status: 'Not filed',
            assigned_to: null,
            recency: '1h',
            action: { label: 'Review case', href: '/dashboard/sansadx?case_id=101' },
            critical: false,
        },
    ],
    government_tracking: { ready: 4, registered: 6, department: 2, resolved: 3, sync_issues: 1, issues: ['#CN-77 · Sync Issue'] },
    presence_map: {
        localities: [
            { name: 'Whitefield', people: 12, complaints: 15, status: 'strong' },
            { name: 'Marathahalli', people: 4, complaints: 5, status: 'growing' },
            { name: 'Varthur', people: 0, complaints: 0, status: 'none' },
        ],
        with_presence: 2, total: 3, gazetteer_known: true,
    },
    issue_pressure: [{ title: 'Water supply', place: 'Whitefield', count: 5 }],
    office_pending: [
        { key: 'letters', label: '2 new letters need intake review', href: '/dashboard/letterbox' },
        { key: 'drafts', label: '1 draft awaiting MP approval', href: '/dashboard/letterbox' },
        { key: 'unassigned', label: '3 unassigned cases need owner', href: '/dashboard/sansadx' },
    ],
    recent_movement: [
        { id: 1, time: '2h', item: 'Govt status changed for #CN-101', tone: 'green', href: '/dashboard/archives' },
    ],
    validation: { thread_count: 9 },
};

let govtDue = [];

describe('MP dashboard overview', () => {
    beforeEach(() => {
        pushMock.mockReset();
        govtDue = [3451, 3459, 3428, 3425, 3412];
        apiPostMock.mockReset();
        apiPostMock.mockImplementation(async (path) => { govtDue = govtDue.filter((id) => !path.includes(`/${id}/`)); return { success: true }; });
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/dashboard/overview') return OVERVIEW;
            if (path === '/api/dashboard/engagements') {
                return { items: [{ id: 1, title: 'Call sanitation officer', starts_at: null, is_all_day: true }] };
            }
            if (path === '/api/news?news_type=local') {
                return { articles: [{ source: 'Belagavi Herald', title: 'Rain floods low-lying lanes', link: 'https://example.com/x' }] };
            }
            if (path === '/api/maps/seat-manifest') return { seat: 'Belagavi South', features: [] };
            if (path === '/api/dashboard/overview/govt-tracking') {
                return {
                    portal: { name: 'CPGRAMS', url: 'https://pgportal.gov.in' }, check_every_days: 14,
                    check: { due: govtDue.length, open_filed: 14, checked_recently_pct: 57, oldest_filed_days: 58,
                        items: govtDue.map((id, i) => ({ id, case_ref: `#${id}`, title: `Filed complaint ${id}`, department: 'HESCOM', reference: `G${id}`, filed_days: 58 - i, last_checked_days: i ? 20 : null })) },
                    departments: { filed: 21, waiting: 14, slowest: 'Public Works Dept', rows: [
                        { name: 'Public Works Dept', filed: 8, waiting: 6, resolved: 2, oldest_wait_days: 58 },
                        { name: 'HESCOM', filed: 2, waiting: 1, resolved: 1, oldest_wait_days: 12 }] },
                    resolved: { window_days: 30, count: 6, previous: 4, avg_days: 22, not_told: 1, items: [
                        { id: 3398, case_ref: '#3398', title: 'Water supply restored', department: 'City Water Board', days_to_resolve: 19, citizen_told: true },
                        { id: 3377, case_ref: '#3377', title: 'Pothole patched', department: 'Public Works Dept', days_to_resolve: 34, citizen_told: false }] },
                };
            }
            if (path.startsWith('/api/dashboard/overview/metrics/new_contacts')) {
                return { key: 'new_contacts', total: 1, contacts: [{ label: 'Asha Patil', name: 'Asha Patil', phone: '+91 98000 03535', first_contact: '2026-11-20T10:00:00', case_count: 2,
                    cases: [{ id: 501, case_ref: 'CN-501', preview: 'Street light not working', category: 'Electricity', locality: 'Tilakwadi', age_days: 5 },
                            { id: 502, case_ref: 'CN-502', preview: 'Drain overflowing', category: 'Drainage', locality: 'Tilakwadi', age_days: 2 }] }] };
            }
            if (path.startsWith('/api/dashboard/overview/metrics/pending')) {
                return { key: 'pending', total: 1, cases: [{ id: 101, case_ref: 'CN-101', preview: 'Pipeline burst', category: 'Water', locality: 'Whitefield', age_days: 1 }] };
            }
            if (path.startsWith('/api/dashboard/overview/metrics')) {
                return { window: { kind: 'days', days: path.includes('days=7') ? 7 : 30 }, metrics: [
                    { key: 'complaints', value: 146, previous: 124 }, { key: 'filed', value: 12, previous: 31 },
                    { key: 'resolved', value: 9, previous: 7 }, { key: 'other_actions', value: 38, previous: 35 },
                    { key: 'pending', value: 96, previous: 71 }, { key: 'new_contacts', value: 60, previous: 99 }] };
            }
            return {};
        });
    });

    it('renders the locked Overview design wired to /api/dashboard/overview', async () => {
        render(<DashboardPage />);

        expect(await screen.findByText('Attention Queue')).toBeInTheDocument();
        expect(screen.getByText('Government Tracking')).toBeInTheDocument();
        expect(screen.getByText('Presence Map')).toBeInTheDocument();
        expect(screen.queryByText('Constituency Pressure')).toBeNull();
        expect(screen.getByText('Varthur')).toBeInTheDocument();
        expect(screen.getByText('No presence')).toBeInTheDocument();
        expect(screen.getByText('Issue Pressure')).toBeInTheDocument();
        expect(screen.getByText('Today')).toBeInTheDocument();
        expect(screen.getByText('Office Pending')).toBeInTheDocument();
        expect(screen.getByText('Recent Movement')).toBeInTheDocument();
        expect(screen.getByText('Local Signals')).toBeInTheDocument();

        expect(screen.getByText('Pipeline burst in Whitefield since morning')).toBeInTheDocument();
        expect(screen.getByText('Review case')).toBeInTheDocument();

        expect(apiGetMock).toHaveBeenCalledWith('/api/dashboard/overview');
    });

    it('shows six clickable numbers; New Contacts opens people with their cases', async () => {
        render(<DashboardPage />);
        const strip = await screen.findByRole('region', { name: 'Key numbers' });
        for (const label of ['Complaints', 'Filed with Government', 'Resolved by Government', 'Other Actions', 'Pending', 'New Contacts']) {
            expect(within(strip).getByText(label)).toBeInTheDocument();
        }
        await within(strip).findByText('146');
        expect(within(strip).getByText('↓ 61%')).toHaveClass('bad');      // fewer filings is bad
        expect(within(strip).getByText('↑ 35%')).toHaveClass('bad');      // more pending is bad
        expect(screen.queryByText('Ready to file', { selector: '.attention-label' })).toBeNull();

        fireEvent.click(within(strip).getByRole('button', { name: /New Contacts: 60/ }));
        const drawer = await screen.findByRole('dialog', { name: /New Contacts/ });
        expect(await within(drawer).findByText('Asha Patil')).toBeInTheDocument();
        expect(within(drawer).getByRole('link', { name: '+91 98000 03535' })).toHaveAttribute('href', 'tel:+919800003535');
        expect(within(drawer).queryByText(/Citizen ···/)).toBeNull();
        expect(within(drawer).getByText('Street light not working')).toBeInTheDocument();
        fireEvent.click(within(drawer).getByText('Drain overflowing'));
        expect(pushMock).toHaveBeenCalledWith('/dashboard/sansadx?case_id=502');
        expect(screen.queryByRole('dialog')).toBeNull();
    });

    it('changes period and closes the list with Escape', async () => {
        render(<DashboardPage />);
        const strip = await screen.findByRole('region', { name: 'Key numbers' });
        fireEvent.click(within(strip).getByRole('button', { name: '7 days' }));
        await waitFor(() => expect(apiGetMock).toHaveBeenCalledWith('/api/dashboard/overview/metrics?days=7'));
        await within(strip).findByText('146');
        fireEvent.click(within(strip).getByRole('button', { name: /Pending: 96/ }));
        const drawer = await screen.findByRole('dialog', { name: /Pending/ });
        expect(apiGetMock).toHaveBeenCalledWith('/api/dashboard/overview/metrics/pending?days=7&limit=100');
        expect(await within(drawer).findByText('Pipeline burst')).toBeInTheDocument();
        fireEvent.keyDown(window, { key: 'Escape' });
        expect(screen.queryByRole('dialog')).toBeNull();
    });

    it('Government Tracking: three compact rows that open on click, and recording a status check', async () => {
        render(<DashboardPage />);
        const card = await screen.findByRole('region', { name: 'Government Tracking' });
        const checkRow = await within(card).findByRole('button', { name: /Check status of filed complaints/ });
        expect(checkRow).toHaveAttribute('aria-expanded', 'false');
        expect(within(card).getByText(/5 not checked in 14 days · oldest filed 58 days ago/)).toBeInTheDocument();
        expect(within(card).getByText(/14 waiting across 2 departments · slowest: Public Works Dept/)).toBeInTheDocument();
        expect(within(card).getByText(/Last 30 days · ↑ 2 vs previous 30 days · 1 citizen not yet told/)).toBeInTheDocument();
        expect(within(card).queryByText('Filed complaint 3451')).toBeNull();          // closed by default

        fireEvent.click(checkRow);
        expect(checkRow).toHaveAttribute('aria-expanded', 'true');
        expect(within(card).getByText('Filed complaint 3451')).toBeInTheDocument();
        expect(within(card).queryByText('Filed complaint 3412')).toBeNull();          // 4 shown until "See all"
        expect(within(card).getAllByRole('link', { name: 'CPGRAMS ↗' })[0]).toHaveAttribute('href', 'https://pgportal.gov.in');
        const first = within(card).getByText('Filed complaint 3451').closest('.gt-chk');
        fireEvent.click(within(first).getByRole('button', { name: 'Resolved' }));
        await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith('/api/cases/3451/govt/check', { outcome: 'resolved' }));
        await waitFor(() => expect(within(card).queryByText('Filed complaint 3451')).toBeNull());
        expect(within(card).getByRole('status')).toHaveTextContent('#3451: recorded “Resolved”.');

        fireEvent.click(within(card).getByRole('button', { name: /Filed complaints, department-wise/ }));
        expect(within(card).getByRole('cell', { name: 'Public Works Dept' })).toBeInTheDocument();
        fireEvent.click(within(card).getByRole('button', { name: /Resolved by Government/ }));
        expect(within(card).getByText('Tell citizen')).toBeInTheDocument();
        fireEvent.click(within(card).getByText('Pothole patched'));
        expect(pushMock).toHaveBeenCalledWith('/dashboard/sansadx?case_id=3377');
    });
});
