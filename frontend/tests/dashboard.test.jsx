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

describe('MP dashboard overview', () => {
    beforeEach(() => {
        pushMock.mockReset();
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/dashboard/summary') {
                return {
                    category_breakdown: { Water: 2 },
                    status_breakdown: { new: 1, resolved: 2 },
                    red_zones: [{ area: 'Whitefield', cnt: 1 }],
                    critical_count: 1,
                };
            }
            if (path === '/api/maps/seat-manifest') {
                return {
                    seat_key: 'mla:belgaum-dakshin',
                    seat_type: 'mla',
                    seat_name: 'Belgaum Dakshin',
                    asset: { type: 'svg', path: '/maps/mla/belgaum-dakshin-outline.svg', aspect_ratio: '72 / 63' },
                    features: [],
                    fallback_anchors: [],
                    status: 'live',
                    version: 1,
                };
            }
            if (path === '/api/activity/report-card') return null;
            if (path.startsWith('/api/dashboard/engagements?')) return { items: [] };
            if (path.startsWith('/api/news?news_type=')) return { articles: [] };
            if (path.startsWith('/api/cases?')) {
                return {
                    cases: [
                        {
                            id: 101,
                            status: 'new',
                            created_at: '2026-05-07T09:00:00Z',
                            raw_message: 'Pipeline burst in Whitefield',
                            category: 'Water',
                        },
                    ],
                };
            }
            return {};
        });
    });

    it('renders the console dashboard overview with MP-facing sections', async () => {
        render(<DashboardPage />);

        expect(await screen.findByText('Grievances open')).toBeInTheDocument();
        expect(screen.getByText('Workload by category')).toBeInTheDocument();
        expect(screen.getByText('Letters & drafts')).toBeInTheDocument();
        expect(screen.getAllByText('Add schedule').length).toBeGreaterThan(0);
        expect(screen.getAllByText('Add note').length).toBeGreaterThan(0);
        expect(screen.getAllByText('Add calendar').length).toBeGreaterThan(0);
        expect(apiGetMock).toHaveBeenCalledWith('/api/dashboard/summary');
    });
});
