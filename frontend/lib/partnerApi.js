import { periodQuery } from './partnerFormat';
/**
 * Partner (consultancy) API client.
 *
 * Deliberately separate from lib/api.js: partner tokens are a different
 * credential from MP/admin tokens (the backend signs them with a derived key),
 * so they live under their own storage keys and never touch `needle_token`.
 * sessionStorage only, so closing the tab signs the partner out.
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

const TOKEN_KEY = 'needle_partner_token';
const BRAND_KEY = 'needle_partner_brand';
const MUST_CHANGE_KEY = 'needle_partner_must_change';
const REQUEST_TIMEOUT = 15000;

export class PartnerApiError extends Error {
    constructor(message, status = 0) {
        super(message);
        this.name = 'PartnerApiError';
        this.status = status;
    }
}

function storage() {
    return typeof window === 'undefined' ? null : window.sessionStorage;
}

export function getPartnerToken() {
    return storage()?.getItem(TOKEN_KEY) || null;
}

export function getStoredPartnerBrand() {
    try {
        return JSON.parse(storage()?.getItem(BRAND_KEY) || 'null');
    } catch {
        return null;
    }
}

export function getMustChangePassword() {
    return storage()?.getItem(MUST_CHANGE_KEY) === '1';
}

export function storePartnerSession({ token, partner, mustChangePassword }) {
    const s = storage();
    if (!s) return;
    if (token) s.setItem(TOKEN_KEY, token);
    if (partner) s.setItem(BRAND_KEY, JSON.stringify(partner));
    if (mustChangePassword === undefined) return;
    if (mustChangePassword) s.setItem(MUST_CHANGE_KEY, '1');
    else s.removeItem(MUST_CHANGE_KEY);
}

export function clearPartnerSession() {
    const s = storage();
    if (!s) return;
    [TOKEN_KEY, BRAND_KEY, MUST_CHANGE_KEY].forEach((k) => s.removeItem(k));
}

function messageFromDetail(detail, fallback) {
    if (typeof detail === 'string' && detail) return detail;
    if (Array.isArray(detail)) return 'Please check the form fields and try again.';
    return fallback;
}

async function request(path, { method = 'GET', body, asText = false, auth = true, timeout = REQUEST_TIMEOUT } = {}) {
    const token = getPartnerToken();
    if (auth && !token) throw new PartnerApiError('Please sign in again.', 401);

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    let res;
    try {
        res = await fetch(`${API_BASE}${path}`, {
            method,
            headers: {
                ...(body ? { 'Content-Type': 'application/json' } : {}),
                ...(auth ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: body ? JSON.stringify(body) : undefined,
            signal: controller.signal,
            cache: 'no-store',
        });
    } catch {
        throw new PartnerApiError('Could not reach the server. Check your connection and try again.', 0);
    } finally {
        clearTimeout(timer);
    }

    if (!res.ok) {
        let detail = null;
        try {
            detail = (await res.json())?.detail;
        } catch {
            /* non-JSON error body */
        }
        if (res.status === 401 && auth) {
            clearPartnerSession();
            throw new PartnerApiError('Your session has expired. Please sign in again.', 401);
        }
        throw new PartnerApiError(messageFromDetail(detail, 'Something went wrong. Please try again.'), res.status);
    }
    return asText ? res.text() : res.json();
}

export const partnerLogin = (email, password) =>
    request('/api/partner/auth/login', { method: 'POST', body: { email, password }, auth: false });

export const partnerChangePassword = (currentPassword, newPassword) =>
    request('/api/partner/auth/change-password', {
        method: 'POST',
        body: { current_password: currentPassword, new_password: newPassword },
    });

export const partnerMe = () => request('/api/partner/me');
// `period` is a period object ({ kind: 'days' | 'all' | 'custom', ... }) or a number of days.
export const partnerClients = (period = 30) => request(`/api/partner/clients?${periodQuery(period)}`);
export const partnerClientSummary = (seatId, period = 30) =>
    request(`/api/partner/clients/${encodeURIComponent(seatId)}/summary?${periodQuery(period)}`);
export const partnerClientReport = (seatId, period = 30) =>
    request(`/api/partner/clients/${encodeURIComponent(seatId)}/report?${periodQuery(period)}`, { asText: true });
// The first overview request after a backend restart builds the geography index (~15s), so allow longer.
export const partnerClientOverview = (seatId) =>
    request(`/api/partner/clients/${encodeURIComponent(seatId)}/dashboard/overview`, { timeout: 60000 });
