import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
}));

const { useSearchParamsMock, useRouterPushMock } = vi.hoisted(() => ({
    useSearchParamsMock: vi.fn(),
    useRouterPushMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
    apiGet: (path) => apiGetMock(path),
    apiPut: vi.fn(),
    apiDelete: vi.fn(),
    apiUpload: vi.fn(),
    apiPatch: vi.fn(),
}));

vi.mock('next/navigation', () => ({
    useSearchParams: () => useSearchParamsMock(),
    useRouter: () => ({
        push: useRouterPushMock,
    }),
}));

vi.mock('next/link', () => ({
    default: ({ href, children, ...props }) => (
        <a href={typeof href === 'string' ? href : '#'} {...props}>
            {children}
        </a>
    ),
}));

import GeographyUploadPage from '@/app/dashboard/shared-geography/workspace/page';

describe('Admin geography page', () => {
    beforeEach(() => {
        useRouterPushMock.mockReset();
        useSearchParamsMock.mockReturnValue({
            get: () => null,
        });
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/admin/constituencies') {
                return { constituencies: ['Bangalore North'] };
            }
            if (path === '/api/admin/mps') {
                return {
                    mps: [
                        {
                            tenant_id: 10,
                            display_name: 'Sanket',
                            parliamentary_constituency: 'Belagavi',
                            seat_label: 'MP Seat',
                        },
                    ],
                };
            }
            if (path === '/api/admin/overrides') {
                return { geo_overrides: {} };
            }
            if (path === '/api/admin/geography/parliamentary?seat_type=mp') {
                return { parliamentary_constituencies: ['Bangalore North'] };
            }
            if (path === '/api/admin/geography/parliamentary?seat_type=mla') {
                return { parliamentary_constituencies: ['Belagavi North'] };
            }
            if (path === '/api/admin/geography/Bangalore%20North/assemblies?seat_type=mp') {
                return { assemblies: ['Yelahanka'] };
            }
            if (path === '/api/admin/geography/Belagavi%20North/assemblies?seat_type=mla') {
                return { assemblies: ['Core Zone'] };
            }
            return { assemblies: [] };
        });
    });

    it('loads saved seat geography across MP and MLA seat types', async () => {
        render(<GeographyUploadPage />);

        expect(await screen.findByText('Core Geography')).toBeInTheDocument();
        expect(await screen.findByText('Advanced Alias Diagnostics')).toBeInTheDocument();
        await waitFor(() => {
            expect(apiGetMock).toHaveBeenCalledWith('/api/admin/mps');
            expect(apiGetMock).toHaveBeenCalledWith('/api/admin/geography/parliamentary?seat_type=mp');
            expect(apiGetMock).toHaveBeenCalledWith('/api/admin/geography/parliamentary?seat_type=mla');
        });

        expect((await screen.findAllByText('Bangalore North')).length).toBeGreaterThan(0);
        expect((await screen.findAllByText('Belagavi North')).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/MP Seat|MLA Seat/).length).toBeGreaterThan(1);
    });

    it('lets operators jump into tenant-aware alias cleanup from the generic workspace', async () => {
        render(<GeographyUploadPage />);

        expect(await screen.findByText('Advanced Alias Diagnostics')).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText('Account / Tenant'), {
            target: { value: '10' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Open Tenant Workspace' }));

        expect(useRouterPushMock).toHaveBeenCalledWith('/dashboard/shared-geography/workspace?tenant_id=10');
    });

    it('shows a tenant-aware reuse flow when opened from launch readiness', async () => {
        useSearchParamsMock.mockReturnValue({
            get: (key) => (key === 'tenant_id' ? '7' : null),
        });
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/admin/constituencies') {
                return { constituencies: ['Belagavi'] };
            }
            if (path === '/api/admin/mps') {
                return {
                    mps: [
                        {
                            tenant_id: 7,
                            display_name: 'Aspirant A',
                            parliamentary_constituency: 'Belagavi',
                            seat_label: 'MP Seat',
                        },
                    ],
                };
            }
            if (path === '/api/admin/overrides') {
                return {
                    geo_overrides: {
                        '7': {
                            'teacher colony': 'Belagavi South',
                            'teachers colony khasbag': 'Belagavi South',
                        },
                    },
                };
            }
            if (path === '/api/admin/mps/7/detail') {
                return {
                    tenant_id: 7,
                    seat_type: 'mp',
                    seat_label: 'MP Seat',
                    profile: {
                        mp_name: 'Aspirant A',
                        constituency: 'Belagavi',
                        seat_type: 'mp',
                        seat_label: 'MP Seat',
                    },
                };
            }
            if (path === '/api/admin/geography/parliamentary?seat_type=mp') {
                return { parliamentary_constituencies: ['Belagavi'] };
            }
            if (path === '/api/admin/geography/parliamentary?seat_type=mla') {
                return { parliamentary_constituencies: [] };
            }
            if (path === '/api/admin/geography/Belagavi/assemblies?seat_type=mp') {
                return { assemblies: ['Belagavi North', 'Belagavi South'] };
            }
            return { assemblies: [] };
        });

        render(<GeographyUploadPage />);

        expect(await screen.findByText('Tenant Geography Setup')).toBeInTheDocument();
        expect(await screen.findByText('1. Core Geography')).toBeInTheDocument();
        expect(await screen.findByText('Manual Matching Corrections')).toBeInTheDocument();
        expect(screen.getByText('Shared geography already present')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Back to launch readiness' })).toHaveAttribute('href', '/dashboard/mps/7/setup');
        expect(screen.getByText('Aspirant A')).toBeInTheDocument();
        expect(screen.getAllByText('Belagavi').length).toBeGreaterThan(0);
        expect(screen.getByRole('button', { name: 'Use existing geography' })).toBeInTheDocument();
        expect(screen.getByText('teacher colony')).toBeInTheDocument();
        expect(screen.getByText('2 manual corrections')).toBeInTheDocument();
        expect(screen.getAllByRole('button', { name: 'Edit' }).length).toBeGreaterThan(0);
        expect(screen.getByRole('button', { name: 'Bulk Add' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Delete All' })).toBeInTheDocument();
    });
});
