import React from 'react';
import { render, screen } from '@testing-library/react';
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

    it('renders the locked Overview design wired to /api/dashboard/overview', async () => {
        render(<DashboardPage />);

        expect(await screen.findByText('Attention Queue')).toBeInTheDocument();
        expect(screen.getByText('Government Tracking')).toBeInTheDocument();
        expect(screen.getByText('Constituency Pressure')).toBeInTheDocument();
        expect(screen.getByText('Issue Pressure')).toBeInTheDocument();
        expect(screen.getByText('Today')).toBeInTheDocument();
        expect(screen.getByText('Office Pending')).toBeInTheDocument();
        expect(screen.getByText('Recent Movement')).toBeInTheDocument();
        expect(screen.getByText('Local Signals')).toBeInTheDocument();

        expect(screen.getByText('Pipeline burst in Whitefield since morning')).toBeInTheDocument();
        expect(screen.getByText('Review case')).toBeInTheDocument();

        expect(apiGetMock).toHaveBeenCalledWith('/api/dashboard/overview');
    });
});
