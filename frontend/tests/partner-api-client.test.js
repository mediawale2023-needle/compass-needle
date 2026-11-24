import { vi } from 'vitest';
import {
    PartnerApiError,
    clearPartnerSession,
    getPartnerToken,
    partnerClientBriefing,
    partnerClientOverview,
    partnerClientSummary,
    partnerClients,
    partnerLogin,
    storePartnerSession,
} from '@/lib/partnerApi';
import * as partnerApiModule from '@/lib/partnerApi';
import { hexToHslTriplet } from '@/lib/partnerFormat';

function jsonResponse(body, status = 200) {
    return { ok: status >= 200 && status < 300, status, json: async () => body, text: async () => JSON.stringify(body) };
}

describe('partner API client', () => {
    it('no longer exposes the retired seat-request call', () => {
        expect(partnerApiModule.partnerRequestSeat).toBeUndefined();
    });

    beforeEach(() => {
        sessionStorage.clear();
        localStorage.clear();
    });

    it('logs in without an Authorization header', async () => {
        const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(jsonResponse({ token: 't1', partner: {} }));
        await partnerLogin('ops@firm.in', 'Secret123');
        const [url, init] = fetchMock.mock.calls[0];
        expect(url).toContain('/api/partner/auth/login');
        expect(init.headers.Authorization).toBeUndefined();
        expect(JSON.parse(init.body)).toEqual({ email: 'ops@firm.in', password: 'Secret123' });
    });

    it('sends the partner token as a Bearer header and never touches the MP token keys', async () => {
        storePartnerSession({ token: 'partner-token', partner: { brand_name: 'X' }, mustChangePassword: false });
        sessionStorage.setItem('needle_token', 'mp-token');
        const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(jsonResponse({ clients: [] }));
        await partnerClients(30);
        expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer partner-token');
        expect(sessionStorage.getItem('needle_token')).toBe('mp-token');
        expect(localStorage.getItem('needle_partner_token')).toBeNull(); // sessionStorage only
    });

    it('requests the briefing for one seat with the period and no tenant parameter', async () => {
        storePartnerSession({ token: 'partner-token', partner: { brand_name: 'X' }, mustChangePassword: false });
        const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(jsonResponse({ briefing: {} }));
        await partnerClientBriefing(7, { kind: 'days', days: 90 });
        const [url, init] = fetchMock.mock.calls[0];
        expect(url).toContain('/api/partner/clients/7/briefing?days=90');
        expect(url).not.toMatch(/tenant/i);
        expect(init.headers.Authorization).toBe('Bearer partner-token');
    });

    it('requests the counts-only overview for one seat with the partner token and no tenant parameter', async () => {
        storePartnerSession({ token: 'partner-token', partner: { brand_name: 'X' }, mustChangePassword: false });
        const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(jsonResponse({ overview: {} }));
        await partnerClientOverview(7);
        const [url, init] = fetchMock.mock.calls[0];
        expect(url).toMatch(/\/api\/partner\/clients\/7\/dashboard\/overview$/);
        expect(init.headers.Authorization).toBe('Bearer partner-token');
        expect(url).not.toMatch(/tenant|tid/i);
    });

    it('does not call the server without a token', async () => {
        const fetchMock = vi.spyOn(global, 'fetch');
        await expect(partnerClients(30)).rejects.toMatchObject({ status: 401 });
        expect(fetchMock).not.toHaveBeenCalled();
    });

    it('clears the stored session on a 401 from an authenticated call', async () => {
        storePartnerSession({ token: 'stale', partner: {}, mustChangePassword: false });
        vi.spyOn(global, 'fetch').mockResolvedValue(jsonResponse({ detail: 'Invalid or expired token' }, 401));
        await expect(partnerClients(30)).rejects.toBeInstanceOf(PartnerApiError);
        expect(getPartnerToken()).toBeNull();
    });

    it('surfaces a login 401 message without clearing anything', async () => {
        vi.spyOn(global, 'fetch').mockResolvedValue(jsonResponse({ detail: 'Invalid credentials' }, 401));
        await expect(partnerLogin('a@b.in', 'x')).rejects.toThrow('Invalid credentials');
    });

    it('turns validation arrays and network failures into readable messages', async () => {
        storePartnerSession({ token: 't', partner: {}, mustChangePassword: false });
        vi.spyOn(global, 'fetch').mockResolvedValueOnce(jsonResponse({ detail: [{ msg: 'too short' }] }, 422));
        await expect(partnerClientSummary(7, 30)).rejects.toThrow(/check the form/i);

        vi.spyOn(global, 'fetch').mockRejectedValueOnce(new TypeError('Failed to fetch'));
        await expect(partnerClients(30)).rejects.toMatchObject({ status: 0 });
    });

    it('clearPartnerSession removes every partner key', () => {
        storePartnerSession({ token: 't', partner: { a: 1 }, mustChangePassword: true });
        clearPartnerSession();
        expect(sessionStorage.length).toBe(0);
    });
});

describe('hexToHslTriplet', () => {
    it('converts valid hex colours and rejects anything else', () => {
        expect(hexToHslTriplet('#FF0000')).toBe('0 100% 50%');
        expect(hexToHslTriplet('#000000')).toBe('0 0% 0%');
        expect(hexToHslTriplet('red; background:url(x)')).toBeNull();
        expect(hexToHslTriplet(undefined)).toBeNull();
    });
});
