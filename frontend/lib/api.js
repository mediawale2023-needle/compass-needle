/**
 * API client — wraps fetch with JWT auth, retries, and timeout.
 * Calls the backend directly using NEXT_PUBLIC_API_URL.
 *
 * DESIGN: Short timeouts + minimal retries to prevent browser freezing.
 * Dashboard pages use .catch() fallbacks so a slow/down backend
 * never blocks the UI.
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const REQUEST_TIMEOUT = 8000;   // 8 seconds for normal data calls
const AI_TIMEOUT = 60000;       // 60 seconds for AI endpoints (Gemini can take 15-30s)
const LOGIN_TIMEOUT = 28000;    // 28 seconds for login (handles cold start / slow wake)
const LOGIN_MAX_RETRIES = 3;    // 3 retries for login so first wake-up can fail
const LOGIN_RETRY_DELAY = 2000; // 2s between login retries
const MAX_RETRIES = 1;         // 1 retry only (2 total attempts) for other calls
const RETRY_DELAY = 500;       // 500ms base delay

function getAuthToken() {
    if (typeof window === 'undefined') return null;
    const token = sessionStorage.getItem('needle_token') || localStorage.getItem('needle_token');
    if (token) {
        sessionStorage.setItem('needle_token', token);
        localStorage.removeItem('needle_token');
    }
    const user = sessionStorage.getItem('needle_user') || localStorage.getItem('needle_user');
    if (user) {
        sessionStorage.setItem('needle_user', user);
        localStorage.removeItem('needle_user');
    }
    return token;
}

function clearAuthToken() {
    if (typeof window === 'undefined') return;
    sessionStorage.removeItem('needle_token');
    sessionStorage.removeItem('needle_user');
    localStorage.removeItem('needle_token');
    localStorage.removeItem('needle_user');
}

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
    const token = getAuthToken();

    // If no token and path requires auth, fail fast instead of making a doomed request
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
                    clearAuthToken();
                    window.location.href = '/';
                }
                throw new Error('Unauthorized');
            }

            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: 'Request failed' }));
                // Don't retry 4xx client errors (except 408/429)
                if (res.status < 500 && res.status !== 408 && res.status !== 429) {
                    throw new Error(err.detail || `HTTP ${res.status}`);
                }
                throw new Error(err.detail || `HTTP ${res.status}`);
            }

            return res.json();
        } catch (err) {
            lastError = err;

            // Don't retry auth errors or client errors
            if (err.message === 'Unauthorized' || err.message === 'No auth token' ||
                (err.message && err.message.startsWith('HTTP 4'))) {
                throw err;
            }

            // Retry on network errors, timeouts, and server errors
            if (attempt < maxRetries) {
                const delay = retryDelayBase * Math.pow(2, attempt);
                await new Promise(r => setTimeout(r, delay));
                continue;
            }
        }
    }

    // Friendly message for login when backend is slow or cold
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

/**
 * Authenticated fetch that returns a Blob (for file downloads).
 * Uses a 30s timeout to allow server-side PDF generation.
 */
export async function apiBlob(path) {
    const token = getAuthToken();
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
            clearAuthToken();
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
