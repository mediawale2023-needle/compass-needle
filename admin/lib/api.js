/**
 * Admin API client — wraps fetch with admin JWT auth, retries, and timeout.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const REQUEST_TIMEOUT = 15000; // 15 seconds
const MAX_RETRIES = 2;         // up to 2 retries (3 total attempts)
const RETRY_DELAY = 800;       // base delay in ms (doubles each retry)

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
    const token = typeof window !== 'undefined' ? localStorage.getItem('admin_token') : null;

    const headers = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
    };

    // Remove Content-Type for FormData (file uploads)
    if (options.body instanceof FormData) {
        delete headers['Content-Type'];
    }

    let lastError = null;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        try {
            const res = await fetchWithTimeout(
                `${API_BASE}${path}`,
                { ...options, headers },
                REQUEST_TIMEOUT,
            );

            if (res.status === 401 || res.status === 403) {
                if (typeof window !== 'undefined') {
                    localStorage.removeItem('admin_token');
                    localStorage.removeItem('admin_user');
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
            if (err.message === 'Unauthorized' || (err.message && err.message.startsWith('HTTP 4'))) {
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

export function apiGet(path) { return api(path, { method: 'GET' }); }
export function apiPost(path, body) { return api(path, { method: 'POST', body: JSON.stringify(body) }); }
export function apiPatch(path, body) { return api(path, { method: 'PATCH', body: JSON.stringify(body) }); }
export function apiPut(path, body) { return api(path, { method: 'PUT', body: JSON.stringify(body) }); }
export function apiDelete(path) { return api(path, { method: 'DELETE' }); }

export async function apiUpload(path, file) {
    const formData = new FormData();
    formData.append('file', file);
    return api(path, { method: 'POST', body: formData });
}
