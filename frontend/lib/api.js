/**
 * API client — wraps fetch with JWT auth, retries, and timeout.
 * Calls the backend directly using NEXT_PUBLIC_API_URL.
 *
 * DESIGN: Short timeouts + minimal retries to prevent browser freezing.
 * Dashboard pages use .catch() fallbacks so a slow/down backend
 * never blocks the UI.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const REQUEST_TIMEOUT = 8000;  // 8 seconds (was 15 — too long)
const MAX_RETRIES = 1;         // 1 retry only (2 total attempts, was 3)
const RETRY_DELAY = 500;       // 500ms base delay

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

    // If no token and path requires auth, fail fast instead of making a doomed request
    if (!token && !path.includes('/auth/') && !path.includes('/health')) {
        throw new Error('No auth token');
    }

    const headers = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
    };

    let lastError = null;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        try {
            const res = await fetchWithTimeout(
                `${API_BASE}${path}`,
                { ...options, headers },
                REQUEST_TIMEOUT,
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
            if (attempt < MAX_RETRIES) {
                const delay = RETRY_DELAY * Math.pow(2, attempt);
                await new Promise(r => setTimeout(r, delay));
                continue;
            }
        }
    }

    throw lastError || new Error('Request failed after retries');
}

export async function apiGet(path) {
    return api(path, { method: 'GET' });
}

export async function apiPost(path, body) {
    return api(path, { method: 'POST', body: JSON.stringify(body) });
}

export async function apiPatch(path, body) {
    return api(path, { method: 'PATCH', body: JSON.stringify(body) });
}
