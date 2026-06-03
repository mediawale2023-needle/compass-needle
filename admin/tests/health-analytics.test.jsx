import React from 'react';
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
    apiGet: (path) => apiGetMock(path),
}));

import TenantHealthPage from '@/app/dashboard/system/health/page';
import UsageAnalyticsPage from '@/app/dashboard/cases-intelligence/analytics/page';

describe('Admin tenant health and usage analytics contracts', () => {
    beforeEach(() => {
        apiGetMock.mockReset();
    });

    it('renders tenant health with backend-shaped fields and aliases', async () => {
        apiGetMock.mockResolvedValue({
            tenants: [
                {
                    id: 42,
                    name: 'Shri Test MP',
                    constituency: 'Koil',
                    health: 'active',
                    last_case: '2026-05-08T08:45:00Z',
                    last_login: '2026-05-08T07:00:00Z',
                    total_cases: 19,
                    open_cases: 3,
                    cases_last_30d: 11,
                },
            ],
        });

        render(<TenantHealthPage />);

        expect(await screen.findByText('Shri Test MP')).toBeInTheDocument();
        expect(screen.getByText('Tenant #42')).toBeInTheDocument();
        expect(screen.getByText('3 open / 19 total')).toBeInTheDocument();
        expect(screen.getByText('11')).toBeInTheDocument();
    });

    it('renders usage analytics with backend-shaped fields and aliases', async () => {
        apiGetMock.mockResolvedValue({
            period: 'May 2026',
            tenants: [
                {
                    tenant_id: 9,
                    name: 'Smt Usage MP',
                    constituency: 'Aligarh',
                    cases_this_month: 7,
                    cases_total: 70,
                    letters_drafted: 3,
                    questions_drafted: 2,
                    docs_analysed: 4,
                    letterbox_items: 5,
                },
            ],
        });

        render(<UsageAnalyticsPage />);

        expect(await screen.findByText('Smt Usage MP')).toBeInTheDocument();
        expect(screen.getByText('Current period:')).toBeInTheDocument();
        expect(screen.getByText('May 2026')).toBeInTheDocument();
        expect(screen.getByText('Tenant #9')).toBeInTheDocument();
        expect(screen.getByText('70')).toBeInTheDocument();
    });
});
