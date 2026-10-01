import React from 'react';
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock, apiPostMock } = vi.hoisted(() => ({ apiGetMock: vi.fn(), apiPostMock: vi.fn() }));

vi.mock('@/lib/api', () => ({
    apiGet: (path) => apiGetMock(path),
    apiPost: (path, body) => apiPostMock(path, body),
}));

vi.mock('next/link', () => ({
    default: ({ href, children, ...props }) => <a href={href} {...props}>{children}</a>,
}));

import WhatsAppInboundPage from '@/components/admin-domains/system/WhatsAppInboundPage';
import WhatsAppOperationsPage from '@/components/admin-domains/system/WhatsAppOperationsPage';

describe('WhatsApp operational retry safety', () => {
    beforeEach(() => {
        apiGetMock.mockReset();
        apiPostMock.mockReset();
    });

    it('offers retry only for confirmed failed inbound rows', async () => {
        apiGetMock.mockResolvedValue({
            summary: {},
            rows: [
                { id: 1, status: 'failed', sender_phone: '111', meta_message_id: 'm1' },
                { id: 2, status: 'processing', sender_phone: '222', meta_message_id: 'm2' },
                { id: 3, status: 'processed', sender_phone: '333', meta_message_id: 'm3' },
            ],
        });
        render(<WhatsAppInboundPage />);

        expect(await screen.findByRole('button', { name: 'Retry' })).toBeInTheDocument();
        expect(screen.getAllByText('Investigate')).toHaveLength(1);
        expect(screen.getByText('Complete')).toBeInTheDocument();
    });

    it('keeps successful resources visible and marks a failed source unavailable', async () => {
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/admin/debug/whatsapp') throw new Error('diagnostics offline');
            if (path.startsWith('/api/admin/whatsapp/outbound')) return { items: [] };
            return { whatsapp: { status: 'green', reason: 'Operational', routing: { status: 'green', tenant_issues: [] } } };
        });
        render(<WhatsAppOperationsPage />);

        expect(await screen.findByText('Some operational data is unavailable')).toBeInTheDocument();
        expect(screen.getByText('WhatsApp is healthy')).toBeInTheDocument();
        expect(screen.getByText('Live Meta diagnostics are unavailable.')).toBeInTheDocument();
        expect(screen.getByText('No pending or failed outbound replies')).toBeInTheDocument();
    });
});
