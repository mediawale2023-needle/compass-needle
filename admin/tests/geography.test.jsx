import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
    apiGet: (path) => apiGetMock(path),
    apiPut: vi.fn(),
    apiDelete: vi.fn(),
    apiUpload: vi.fn(),
}));

import GeographyUploadPage from '@/app/dashboard/geography/page';

describe('Admin geography page', () => {
    beforeEach(() => {
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/admin/constituencies') {
                return { constituencies: ['Bangalore North'] };
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

        expect(await screen.findByText('Upload Shared Seat Geography')).toBeInTheDocument();
        await waitFor(() => {
            expect(apiGetMock).toHaveBeenCalledWith('/api/admin/geography/parliamentary?seat_type=mp');
            expect(apiGetMock).toHaveBeenCalledWith('/api/admin/geography/parliamentary?seat_type=mla');
        });

        expect((await screen.findAllByText('Bangalore North')).length).toBeGreaterThan(0);
        expect((await screen.findAllByText('Belagavi North')).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/MP Seat|MLA Seat/).length).toBeGreaterThan(1);
    });
});
