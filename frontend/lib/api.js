/**
 * API client — wraps fetch with JWT auth and error handling.
 * Calls the backend directly using NEXT_PUBLIC_API_URL.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

export async function api(path, options = {}) {
    const token = typeof window !== 'undefined' ? localStorage.getItem('needle_token') : null;

    const headers = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
    };

    const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
    });

    if (res.status === 401) {
        // Token expired — redirect to login
        if (typeof window !== 'undefined') {
            localStorage.removeItem('needle_token');
            localStorage.removeItem('needle_user');
            window.location.href = '/';
        }
        throw new Error('Unauthorized');
    }

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }

    return res.json();
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
