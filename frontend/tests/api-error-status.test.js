import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Shared API-client prerequisite for the Delhi frontend: api() errors expose the HTTP status as `error.status`
// (Delhi components branch on 400/403/404/409/502). Messages, retry behaviour and the 401 path must not change.

import { api, apiPost } from '@/lib/api';

function respond(status, body) {
    return {
        status,
        ok: status >= 200 && status < 300,
        json: async () => {
            if (body === undefined) throw new Error('no body');
            return body;
        },
    };
}

let fetchMock;
beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    sessionStorage.setItem('needle_token', 'test-token');
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => {
    vi.unstubAllGlobals();
});

async function failure(promise) {
    try {
        await promise;
    } catch (e) {
        return e;
    }
    throw new Error('expected the request to be rejected');
}

describe('api(): HTTP error status is exposed and the message is unchanged', () => {
    it.each([
        [400, 'Delhi filing support is not available for this case.'],
        [403, 'Manual reference capture isn\'t enabled.'],
        [409, 'This case already has a different government record.'],
        [404, 'Case not found'],
        [502, 'AI drafting failed - try again in a moment'],
    ])('HTTP %i: error.status equals the HTTP status and the server message is kept verbatim', async (status, detail) => {
        fetchMock.mockResolvedValue(respond(status, { detail }));
        const e = await failure(apiPost('/api/cases/1/govt/manual-reference', { reference_number: '1' }, { noRetry: true }));
        expect(e).toBeInstanceOf(Error);
        expect(e.status).toBe(status);
        expect(e.message).toBe(detail);
    });

    it.each([[400], [403], [409]])('HTTP %i without a detail falls back to the existing "HTTP n" message', async (status) => {
        fetchMock.mockResolvedValue(respond(status, {}));
        const e = await failure(api('/api/anything', { noRetry: true }));
        expect(e.status).toBe(status);
        expect(e.message).toBe(`HTTP ${status}`);
    });

    it.each([[400], [403], [409]])('HTTP %i with an unreadable body keeps the existing "Request failed" message', async (status) => {
        fetchMock.mockResolvedValue(respond(status, undefined));
        const e = await failure(api('/api/anything', { noRetry: true }));
        expect(e.status).toBe(status);
        expect(e.message).toBe('Request failed');
    });

    it('a 403 "Password reset required" still redirects exactly as before and now also carries the status', async () => {
        fetchMock.mockResolvedValue(respond(403, { detail: 'Password reset required' }));
        const e = await failure(api('/api/anything', { noRetry: true }));
        expect(sessionStorage.getItem('needle_force_reset_required')).toBe('1');
        expect(e.message).toBe('Password reset required');
        expect(e.status).toBe(403);
    });
});

describe('api(): unchanged behaviour', () => {
    it('401 path is untouched: "Unauthorized", no status property, token cleared', async () => {
        fetchMock.mockResolvedValue(respond(401, { detail: 'nope' }));
        const e = await failure(api('/api/anything', { noRetry: true }));
        expect(e.message).toBe('Unauthorized');
        expect(e.status).toBeUndefined();
        expect(sessionStorage.getItem('needle_token')).toBeNull();
    });

    it('no token: still fails fast with "No auth token" and no status', async () => {
        sessionStorage.clear();
        const e = await failure(api('/api/anything'));
        expect(e.message).toBe('No auth token');
        expect(e.status).toBeUndefined();
        expect(fetchMock).not.toHaveBeenCalled();
    });

    it('a successful response is returned as-is', async () => {
        fetchMock.mockResolvedValue(respond(200, { ok: true }));
        await expect(api('/api/anything')).resolves.toEqual({ ok: true });
    });

    it('retry behaviour is unchanged: a 4xx with a server message is retried once, one without ("HTTP 4xx") is not', async () => {
        fetchMock.mockResolvedValue(respond(409, { detail: 'conflict text' }));
        const withDetail = await failure(api('/api/anything'));
        expect(withDetail.status).toBe(409);
        expect(fetchMock).toHaveBeenCalledTimes(2);       // pre-existing: only messages starting "HTTP 4" skip the retry
        fetchMock.mockClear();
        fetchMock.mockResolvedValue(respond(409, {}));
        const noDetail = await failure(api('/api/anything'));
        expect(noDetail.message).toBe('HTTP 409');
        expect(noDetail.status).toBe(409);
        expect(fetchMock).toHaveBeenCalledTimes(1);
    });
});
