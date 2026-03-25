/**
 * API client for Ambassador — wraps fetch with JWT auth, retries, and timeout.
 * Points to the same backend as Compass Needle via NEXT_PUBLIC_API_URL.
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const REQUEST_TIMEOUT = 8000;
const AI_TIMEOUT = 60000;
const LOGIN_TIMEOUT = 28000;
const LOGIN_MAX_RETRIES = 3;
const LOGIN_RETRY_DELAY = 2000;
const MAX_RETRIES = 1;
const RETRY_DELAY = 500;

async function fetchWithTimeout(url, options, timeout) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
        return await fetch(url, { ...options, signal: controller.signal });
    } finally {
        clearTimeout(timer);
    }
}

export async function api(path, options = {}) {
    const token = typeof window !== 'undefined' ? localStorage.getItem('needle_token') : null;

    if (!token && !path.includes('/auth/') && !path.includes('/health')) {
        throw new Error('No auth token');
    }

    const headers = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
    };

    const timeout = options.timeout ?? (path.includes('/auth/login') ? LOGIN_TIMEOUT : REQUEST_TIMEOUT);
    const maxRetries = options.noRetry ? 0 : (options.maxRetries ?? (path.includes('/auth/login') ? LOGIN_MAX_RETRIES : MAX_RETRIES));
    const retryDelayBase = path.includes('/auth/login') ? LOGIN_RETRY_DELAY : RETRY_DELAY;
    let lastError = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            const res = await fetchWithTimeout(
                `${API_BASE}${path}`,
                { ...options, headers },
                timeout,
            );

            if (res.status === 401) {
                if (typeof window !== 'undefined') {
                    localStorage.removeItem('needle_token');
                    localStorage.removeItem('needle_user');
                    window.location.href = '/';
                }
                throw new Error('Unauthorized');
            }

            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: 'Request failed' }));
                if (res.status < 500 && res.status !== 408 && res.status !== 429) {
                    throw new Error(err.detail || `HTTP ${res.status}`);
                }
                throw new Error(err.detail || `HTTP ${res.status}`);
            }

            return res.json();
        } catch (err) {
            lastError = err;

            if (err.message === 'Unauthorized' || err.message === 'No auth token' ||
                (err.message && err.message.startsWith('HTTP 4'))) {
                throw err;
            }

            if (attempt < maxRetries) {
                const delay = retryDelayBase * Math.pow(2, attempt);
                await new Promise(r => setTimeout(r, delay));
                continue;
            }
        }
    }

    const isLogin = path.includes('/auth/login');
    const isNetworkOrTimeout = lastError?.name === 'AbortError' || lastError?.name === 'TypeError' ||
        lastError?.message === 'Failed to fetch' || (typeof lastError?.message === 'string' && (lastError.message.includes('retries') || lastError.message.includes('Load failed')));
    if (isLogin && isNetworkOrTimeout) {
        throw new Error('Connection timed out or unreachable. The server may be starting — please try again in a moment.');
    }
    throw lastError || new Error('Request failed after retries');
}

export async function apiGet(path) {
    return api(path, { method: 'GET' });
}

export async function apiPost(path, body, opts = {}) {
    return api(path, { method: 'POST', body: JSON.stringify(body), ...opts });
}

export async function apiPatch(path, body) {
    return api(path, { method: 'PATCH', body: JSON.stringify(body) });
}

export async function apiDelete(path) {
    return api(path, { method: 'DELETE' });
}

export async function apiBlob(path) {
    const token = typeof window !== 'undefined' ? localStorage.getItem('needle_token') : null;
    if (!token) throw new Error('No auth token');

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30000);
    try {
        const res = await fetch(`${API_BASE}${path}`, {
            method: 'GET',
            headers: { Authorization: `Bearer ${token}` },
            signal: controller.signal,
        });
        if (res.status === 401) {
            localStorage.removeItem('needle_token');
            localStorage.removeItem('needle_user');
            window.location.href = '/';
            throw new Error('Unauthorized');
        }
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return res.blob();
    } finally {
        clearTimeout(timer);
    }
}

export { AI_TIMEOUT };
