import React from 'react';
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
}));

vi.mock('@/lib/auth', () => ({
    useAuth: () => ({
        user: {
            role: 'mp',
            display_name: 'Arun Kumar',
            theme_color: '#006a4d',
        },
    }),
}));

vi.mock('@/lib/api', () => ({
    apiGet: (path) => apiGetMock(path),
}));

import ArchivesPage from '@/app/dashboard/archives/page';

describe('Archives page', () => {
    beforeEach(() => {
        apiGetMock.mockReset();
    });

    it('renders saved draft letters from history', async () => {
        apiGetMock.mockResolvedValue({
            items: [
                {
                    id: 1,
                    activity_type: 'draft_letter',
                    title: 'Road repair letter',
                    content: 'Please repair the road.',
                    metadata: { recipient: 'Collector' },
                    created_at: '2026-05-24T10:00:00Z',
                },
            ],
        });

        render(<ArchivesPage />);

        expect(await screen.findByText('Road repair letter')).toBeInTheDocument();
        expect(screen.getByText('Letter')).toBeInTheDocument();
        expect(apiGetMock).toHaveBeenCalledWith('/api/history');
    });
});
