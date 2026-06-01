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

describe('Admin seat maps page', () => {
    beforeEach(() => {
        apiGetMock.mockReset();
        apiPostMock.mockReset();
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/admin/seat-maps') {
                return {
                    items: [
                        {
                            seat_key: 'mla:belgaum-dakshin',
                            seat_type: 'mla',
                            seat_name: 'Belgaum Dakshin',
                            state: 'Karnataka',
                            aliases: ['Belgaum Dakshin', 'Belgaum South'],
                            asset: { type: 'svg', path: '/maps/mla/belgaum-dakshin-outline.svg', aspect_ratio: '72 / 63' },
                            features: [
                                {
                                    feature_key: 'nath-pai-circle',
                                    label: 'Nath Pai Circle',
                                    aliases: ['nath pai circle'],
                                    anchor: { x: 68, y: 40 },
                                },
                            ],
                            fallback_anchors: [{ x: 25, y: 26 }],
                            status: 'live',
                            version: 1,
                            source: 'repo',
                        },
                    ],
                };
            }
            return {};
        });
        apiPostMock.mockResolvedValue({
            manifest: {
                seat_key: 'mla:belgaum-dakshin',
                seat_type: 'mla',
                seat_name: 'Belgaum Dakshin',
                state: 'Karnataka',
                aliases: ['Belgaum Dakshin', 'Belgaum South'],
                asset: { type: 'svg', path: '/maps/mla/belgaum-dakshin-outline.svg', aspect_ratio: '72 / 63' },
                features: [
                    {
                        feature_key: 'nath-pai-circle',
                        label: 'Nath Pai Circle',
                        aliases: ['nath pai circle'],
                        anchor: { x: 68, y: 40 },
                    },
                ],
                fallback_anchors: [{ x: 25, y: 26 }],
                status: 'live',
                version: 2,
                source: 'admin',
            },
        });
    });

    it('loads seat manifests and saves through the admin API', async () => {
        render(<SeatMapsPage />);

        expect(await screen.findByDisplayValue('mla:belgaum-dakshin')).toBeInTheDocument();
        expect(screen.getByDisplayValue('Belgaum Dakshin')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Save manifest' }));

        await waitFor(() => {
            expect(apiPostMock).toHaveBeenCalledWith('/api/admin/seat-maps', expect.objectContaining({
                seat_key: 'mla:belgaum-dakshin',
                seat_type: 'mla',
                status: 'live',
            }));
        });

        expect(await screen.findByText('Saved mla:belgaum-dakshin')).toBeInTheDocument();
    });
});
