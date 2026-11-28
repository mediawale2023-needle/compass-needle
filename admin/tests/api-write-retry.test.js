import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { apiGet, apiPost, apiPatch } from '@/lib/api';

// Admin writes (retry a failed WhatsApp send, erase a citizen) must not be repeated
// by the client after a timeout or 5xx; reads are retried once.

const fail500 = () => ({ status: 500, ok: false, json: async () => ({ detail: 'Server busy' }) });
const ok = (body) => ({ status: 200, ok: true, json: async () => body });

let fetchMock;
beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('admin_token', 't');
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe('admin client retries', () => {
    it('sends a write once', async () => {
        fetchMock.mockResolvedValue(fail500());
        await expect(apiPost('/api/admin/whatsapp/outbound/1/retry', {})).rejects.toThrow();
        expect(fetchMock).toHaveBeenCalledTimes(1);
        fetchMock.mockClear();
        fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
        await expect(apiPatch('/api/admin/tenants/1', {})).rejects.toThrow();
        expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('retries a read once', async () => {
        fetchMock.mockResolvedValueOnce(fail500()).mockResolvedValueOnce(ok({ fine: true }));
        await expect(apiGet('/api/admin/tenants')).resolves.toEqual({ fine: true });
        expect(fetchMock).toHaveBeenCalledTimes(2);
    });
});
