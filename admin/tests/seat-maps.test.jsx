import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock, apiPostMock } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
    apiPostMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
    apiGet: (path) => apiGetMock(path),
    apiPost: (path, body) => apiPostMock(path, body),
}));

import SeatMapsPage from '@/app/dashboard/seat-maps/page';

describe('Admin seat maps workflow page', () => {
    beforeEach(() => {
        apiGetMock.mockReset();
        apiPostMock.mockReset();
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/admin/seat-maps/workflow') {
                return {
                    items: [
                        {
                            seat_key: 'mla:Belgaum Dakshin',
                            seat_type: 'mla',
                            seat_name: 'Belgaum Dakshin',
                            state: 'Karnataka',
                            tenant_count: 2,
                            tenants: [
                                { tenant_id: 10, name: 'Sanket', account_stage: 'aspirant' },
                                { tenant_id: 11, name: 'Arun', account_stage: 'elected' },
                            ],
                            assembly_count: 2,
                            locality_count: 24,
                            geography_ready: true,
                            map_ready: false,
                            map_status: null,
                            map_source: null,
                            generated: false,
                            manifest: null,
                        },
                    ],
                };
            }
            return {};
        });
        apiPostMock.mockResolvedValue({
            manifest: {
                seat_key: 'mla:Belgaum Dakshin',
                seat_type: 'mla',
                seat_name: 'Belgaum Dakshin',
                state: 'Karnataka',
                aliases: ['Belgaum Dakshin'],
                asset: {
                    type: 'generated-svg',
                    aspect_ratio: '100 / 72',
                    inline_svg: '<svg />',
                    generated: true,
                },
                features: [],
                fallback_anchors: [],
                status: 'draft',
                version: 1,
                source: 'generated',
            },
        });
    });

    it('loads seat workflow and generates a map in one click', async () => {
        render(<SeatMapsPage />);

        expect(await screen.findByDisplayValue('Belgaum Dakshin')).toBeInTheDocument();
        expect(screen.getByText('Ready to generate')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Generate map' }));

        await waitFor(() => {
            expect(apiPostMock).toHaveBeenCalledWith('/api/admin/seat-maps/generate', expect.objectContaining({
                seat_type: 'mla',
                seat_name: 'Belgaum Dakshin',
            }));
        });

        expect(await screen.findByText('Generated mla:Belgaum Dakshin')).toBeInTheDocument();
    });
});
