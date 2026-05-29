import React from 'react';
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
    apiGet: (path) => apiGetMock(path),
}));

vi.mock('next/link', () => ({
    default: ({ href, children, ...props }) => (
        <a href={typeof href === 'string' ? href : '#'} {...props}>
            {children}
        </a>
    ),
}));

import DashboardOverview from '@/app/dashboard/page';

describe('Admin dashboard overview', () => {
    beforeEach(() => {
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/admin/system-health') {
                return {
                    last_checked: '2026-05-08T09:00:00Z',
                    whatsapp: { status: 'green', last_webhook: '2026-05-08T08:45:00Z' },
                    openai: { status: 'green', configured: true },
                    gemini: { status: 'amber', configured: false },
                };
            }
            if (path === '/api/admin/stats') {
                return {
                    total_accounts: 2,
                    mp_seats: 1,
                    mla_seats: 1,
                    aspirants: 1,
                    total_profiles: 2,
                    total_cases: 14,
                };
            }
            if (path === '/api/admin/mps') {
                return {
                    mps: [
                        {
                            tenant_id: 1,
                            display_name: 'Arun Kumar',
                            username: 'mp_arun',
                            house: 'Lok Sabha',
                            seat_type: 'mp',
                            account_stage: 'elected',
                            seat_label: 'MP',
                            parliamentary_constituency: 'Bangalore North',
                            completeness: 82,
                        },
                    ],
                };
            }
            return {};
        });
    });

    it('renders admin stats and account cards from the API', async () => {
        render(<DashboardOverview />);

        expect(await screen.findByText('Arun Kumar')).toBeInTheDocument();
        expect(screen.getByText('Total Accounts')).toBeInTheDocument();
        expect(screen.getByText('System Health')).toBeInTheDocument();
        expect(screen.getByText('+ Add Account')).toBeInTheDocument();
    });
});
