import React from 'react';
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock, apiPatchMock, apiDeleteMock } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
    apiPatchMock: vi.fn(),
    apiDeleteMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
    apiGet: (path) => apiGetMock(path),
    apiPatch: (path, body) => apiPatchMock(path, body),
    apiDelete: (path) => apiDeleteMock(path),
}));

vi.mock('next/navigation', () => ({
    useSearchParams: () => ({
        get: (key) => (key === 'tenant_id' ? '7' : null),
    }),
}));

vi.mock('next/link', () => ({
    default: ({ href, children, ...props }) => (
        <a href={typeof href === 'string' ? href : '#'} {...props}>
            {children}
        </a>
    ),
}));

import ProfileEditorPage from '@/components/admin-domains/accounts/ProfileEditorPage';

describe('Admin profile editor ownership boundaries', () => {
    beforeEach(() => {
        apiPatchMock.mockReset();
        apiDeleteMock.mockReset();
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/admin/mps') {
                return {
                    mps: [
                        {
                            tenant_id: 7,
                            user_id: 70,
                            display_name: 'Aspirant A',
                            username: 'aspirant_a',
                            role: 'owner',
                            parliamentary_constituency: 'Belagavi',
                            account_stage: 'aspirant',
                            seat_type: 'mp',
                            house: 'Lok Sabha',
                        },
                    ],
                };
            }
            if (path === '/api/admin/constituencies') {
                return { constituencies: ['Belagavi'] };
            }
            if (path === '/api/admin/mps/7/profile') {
                return {
                    exists: true,
                    mp_name: 'Aspirant A',
                    constituency: 'Belagavi',
                    state: 'Karnataka',
                    house: 'Lok Sabha',
                    account_stage: 'aspirant',
                    seat_type: 'mp',
                    party: 'Independent',
                    key_facts: [],
                    languages: ['English', 'Hindi'],
                    alt_names: [],
                    sovereignty_rules: '',
                    vocabulary_guide: {},
                    whatsapp_number: '+919876543210',
                    phone_number_id: '12345',
                };
            }
            return {};
        });
    });

    it('links duplicate WhatsApp and geography work to canonical tenant surfaces', async () => {
        render(<ProfileEditorPage />);

        expect((await screen.findAllByText('Aspirant A')).length).toBeGreaterThan(0);

        expect(screen.getByRole('link', { name: 'Open WhatsApp settings' }))
            .toHaveAttribute('href', '/dashboard/mps/7#whatsapp');
        expect(screen.getByRole('link', { name: 'Open geography workspace' }))
            .toHaveAttribute('href', '/dashboard/shared-geography/workspace?tenant_id=7');
        expect(screen.queryByRole('button', { name: 'Save WhatsApp Config' })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /Save .* Localities/ })).not.toBeInTheDocument();
    });
});
