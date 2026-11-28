import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api, apiGet, apiPost, isRetrySafeMethod } from '@/lib/api';

// A timed-out or 5xx write may already have happened on the server (a citizen
// message sent). The client must not repeat it; reads are still retried once.

const fail500 = () => ({ status: 500, ok: false, json: async () => ({ detail: 'Server busy' }) });
const ok = (body) => ({ status: 200, ok: true, json: async () => body });

let fetchMock;
beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('needle_token', 't');
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe('client retries', () => {
    it('never repeats a POST, PATCH, PUT or DELETE', async () => {
        for (const method of ['POST', 'PATCH', 'PUT', 'DELETE']) {
            fetchMock.mockReset();
            fetchMock.mockResolvedValue(fail500());
            await expect(api('/api/cases/1/notify/send', { method, body: '{}' })).rejects.toThrow('Server busy');
            expect(fetchMock).toHaveBeenCalledTimes(1);
        }
    });

    it('does not repeat a write after a network failure, even with maxRetries set', async () => {
        fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
        await expect(apiPost('/api/cases/1/notify/send', {}, { maxRetries: 3 })).rejects.toThrow();
        expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('still retries a read once', async () => {
        fetchMock.mockResolvedValueOnce(fail500()).mockResolvedValueOnce(ok({ fine: true }));
        await expect(apiGet('/api/cases')).resolves.toEqual({ fine: true });
        expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    it('treats only GET and HEAD as safe to retry', () => {
        expect(isRetrySafeMethod(undefined)).toBe(true);
        expect(isRetrySafeMethod('get')).toBe(true);
        expect(isRetrySafeMethod('HEAD')).toBe(true);
        expect(isRetrySafeMethod('POST')).toBe(false);
    });
});
