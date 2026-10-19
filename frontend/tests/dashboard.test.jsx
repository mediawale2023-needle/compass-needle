import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock, pushMock } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
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
        { key: 'ready_to_file', label: 'Ready to file', value: 41, tone: 'green' },
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
            bucket: 'needs_review',
            latest_citizen_message_at: '2026-10-19T04:44:00Z',
        },
        {
            id: 102,
            case_ref: '#CN-102',
            thread_count: 1,
            message: 'Streetlight not working near the temple',
            issue: 'Electricity',
            location: 'Tilakwadi',
            state: 'Unassigned',
            action: { label: 'File grievance', href: '/dashboard/sansadx?case_id=102' },
            critical: true,
            bucket: 'ready_to_file',
            created_at: '2026-10-18T10:00:00Z',
        },
    ],
    government_tracking: { ready: 4, registered: 6, department: 2, resolved: 3, sync_issues: 1, issues: ['#CN-77 · Sync Issue'] },
    constituency_pressure: [{ name: 'Whitefield', count: 5 }],
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

describe('MP dashboard overview', () => {
    beforeEach(() => {
        pushMock.mockReset();
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/dashboard/overview') return OVERVIEW;
            if (path === '/api/dashboard/engagements') {
                return { items: [{ id: 1, title: 'Call sanitation officer', starts_at: null, is_all_day: true }] };
            }
            if (path === '/api/news?news_type=local') {
                return { articles: [{ source: 'Belagavi Herald', title: 'Rain floods low-lying lanes', link: 'https://example.com/x' }] };
            }
            if (path === '/api/maps/seat-manifest') return { seat: 'Belagavi South', features: [] };
            return {};
        });
    });

    it('renders the Operations Dashboard overview wired to /api/dashboard/overview', async () => {
        render(<DashboardPage />);

        expect(await screen.findByRole('heading', { name: 'Overview', level: 1 })).toBeInTheDocument();
        for (const title of ['Attention Queue', 'Government Tracking', 'Constituency Pressure', 'Top Issues',
            'Department Response Time', 'Recent Activity', 'Today', 'Office Pending', 'Local Signals']) {
            expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
        }
        expect(screen.getByText('Pipeline burst in Whitefield since morning')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Review case' })).toBeInTheDocument();
        expect(apiGetMock).toHaveBeenCalledWith('/api/dashboard/overview');
    });

    it('labels the two "ready" counts distinctly: KPI = portal-prepared stage, context = not yet filed', async () => {
        render(<DashboardPage />);
        const kpis = await screen.findByLabelText('Key counts');
        const ready = within(kpis).getByText('Ready to file').closest('a');
        // government_tracking.ready (4), not the broad not-filed attention bucket (41)
        expect(within(ready).getByText('4')).toBeInTheDocument();
        expect(within(ready).getByText('Prepared for portal · 41 active not yet filed')).toBeInTheDocument();
        expect(within(kpis).getByText('Needs review').closest('a')).toHaveAttribute('href', '/dashboard/sansadx?status=pending_review');
        expect(within(kpis).getByText('Needs location').closest('a')).toHaveAttribute('href', '/dashboard/sansadx?status=awaiting_location');
    });

    it('filters the Attention Queue by bucket and shows the real bucket total', async () => {
        render(<DashboardPage />);
        await screen.findByText('Streetlight not working near the temple');
        fireEvent.click(screen.getByRole('tab', { name: /Needs review/ }));
        expect(screen.getByText('Pipeline burst in Whitefield since morning')).toBeInTheDocument();
        expect(screen.queryByText('Streetlight not working near the temple')).toBeNull();
        expect(screen.getByText('Showing 1 of 3 (latest items only).')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('tab', { name: /Not yet filed/ }));
        expect(screen.getByText('Streetlight not working near the temple')).toBeInTheDocument();
    });

    it('never shows fabricated department response metrics', async () => {
        render(<DashboardPage />);
        expect(await screen.findByText(/Response-time analytics will appear once government filing and response timestamps are available/)).toBeInTheDocument();
    });
});
