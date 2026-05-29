import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock, apiPatchMock } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
    apiPatchMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
    apiGet: (path) => apiGetMock(path),
    apiPatch: (path, body) => apiPatchMock(path, body),
}));

vi.mock('next/navigation', () => ({
    useParams: () => ({ tenant_id: '7' }),
}));

vi.mock('next/link', () => ({
    default: ({ href, children, ...props }) => (
        <a href={typeof href === 'string' ? href : '#'} {...props}>
            {children}
        </a>
    ),
}));

import SetupChecklistPage from '@/app/dashboard/mps/[tenant_id]/setup/page';

describe('Admin MP setup checklist', () => {
    beforeEach(() => {
        apiPatchMock.mockReset();
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/admin/mps/7/detail') {
                return {
                    tenant_id: 7,
                    profile: {
                        mp_name: 'Shri Jagdish Shettar',
                        constituency: 'Belagavi',
                        state: 'Karnataka',
                        house: 'Lok Sabha',
                        key_facts: ['Border district'],
                        whatsapp_number: '+919876543210',
                        phone_number_id: '',
                    },
                    staff: [{ username: 'pa_one', is_active: true }],
                    onboarding_state: {},
                };
            }
            if (path === '/api/admin/mps/7/geography') {
                return { assemblies: { 'Belgaum Uttar': ['Hanuman Nagar', 'Tilakwadi'] } };
            }
            return {};
        });
    });

    it('shows real readiness blockers and only lets operators verify smoke tests manually', async () => {
        apiPatchMock.mockResolvedValue({ onboarding_state: { test_sent: true } });

        render(<SetupChecklistPage />);

        expect(await screen.findByText('Tenant Launch Readiness')).toBeInTheDocument();
        expect(screen.getByText('Blocked: WhatsApp Routing Ready, Live Smoke Test Completed')).toBeInTheDocument();
        expect(screen.getByText('Missing Meta phone number ID')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Enable Production Traffic' })).toBeDisabled();

        fireEvent.click(screen.getByRole('button', { name: 'Mark verified' }));

        await waitFor(() => {
            expect(apiPatchMock).toHaveBeenCalledWith('/api/admin/mps/7/onboarding', { test_sent: true });
        });
    });

    it('routes the geography checklist action to the dedicated geography page', async () => {
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/admin/mps/7/detail') {
                return {
                    tenant_id: 7,
                    profile: {
                        mp_name: 'Shri Jagdish Shettar',
                        constituency: 'Belagavi',
                        state: 'Karnataka',
                        house: 'Lok Sabha',
                        key_facts: ['Border district'],
                        whatsapp_number: '+919876543210',
                        phone_number_id: '',
                    },
                    staff: [{ username: 'pa_one', is_active: true }],
                    onboarding_state: {},
                };
            }
            if (path === '/api/admin/mps/7/geography') {
                return { assemblies: {} };
            }
            return {};
        });

        render(<SetupChecklistPage />);

        const link = await screen.findByRole('link', { name: 'Configure geography →' });
        expect(link).toHaveAttribute('href', '/dashboard/geography?tenant_id=7');
    });
});
