/**
 * Admin API client — wraps fetch with admin JWT auth.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

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

    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

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
        throw new Error(err.detail || `HTTP ${res.status}`);
    }

    return res.json();
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
