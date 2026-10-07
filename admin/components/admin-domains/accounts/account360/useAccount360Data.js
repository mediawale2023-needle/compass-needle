'use client';

import { useCallback, useEffect, useState } from 'react';
import { apiGet } from '@/lib/api';

/**
 * Loads every real source Account 360 reads. Each resource loads and fails
 * independently; `detail` is the only one the page cannot render without.
 */
export function useAccount360Data(tenantId) {
    const [data, setData] = useState({});
    const [status, setStatus] = useState({});

    const load = useCallback(async (key, path, select = (value) => value) => {
        setStatus((current) => ({ ...current, [key]: 'loading' }));
        try {
            const result = await apiGet(path);
            setData((current) => ({ ...current, [key]: select(result) }));
            setStatus((current) => ({ ...current, [key]: 'ready' }));
            return result;
        } catch (error) {
            setStatus((current) => ({ ...current, [key]: 'error' }));
            return null;
        }
    }, []);

    const loaders = useCallback(() => ({
        detail: () => load('detail', `/api/admin/mps/${tenantId}/detail`),
        notes: () => load('notes', `/api/admin/mps/${tenantId}/notes`, (r) => r?.notes || []),
        support: () => load('support', `/api/admin/mps/${tenantId}/support-access`, (r) => r?.requests || []),
        geography: () => load('geography', `/api/admin/mps/${tenantId}/geography`, (r) => r || { assemblies: {} }),
        cases: () => load('cases', `/api/admin/cases/aggregates?weeks=12&tenant_id=${encodeURIComponent(tenantId)}`),
        health: () => load('health', '/api/admin/system-health'),
        outbound: () => load('outbound', `/api/admin/whatsapp/outbound?tenant_id=${encodeURIComponent(tenantId)}&page=1&page_size=100`, (r) => r?.items || []),
        alerts: () => load('alerts', '/api/admin/alerts', (r) => r?.alerts || []),
        parliament: () => load('parliament', '/api/admin/parliament/sync/status'),
    }), [load, tenantId]);

    useEffect(() => {
        const all = loaders();
        Object.values(all).forEach((fn) => fn());
    }, [loaders]);

    // Seat-level geography decisions need the seat key from the profile.
    const seatKey = data.detail
        ? (() => {
            const seatType = data.detail.seat_type || data.detail.profile?.seat_type;
            const constituency = data.detail.profile?.constituency;
            return seatType && constituency && constituency !== 'India' ? `${seatType}:${constituency}` : null;
        })()
        : null;
    useEffect(() => {
        if (seatKey) load('decisions', `/api/admin/seats/geography-decisions?seat_key=${encodeURIComponent(seatKey)}&limit=30`, (r) => r?.items || []);
    }, [seatKey, load]);

    // Support-access requests are polled, as before (tenant approvals arrive async).
    useEffect(() => {
        const id = window.setInterval(() => { loaders().support(); }, 15000);
        return () => window.clearInterval(id);
    }, [loaders]);

    const reload = useCallback((key) => loaders()[key]?.(), [loaders]);
    const setLocal = useCallback((key, value) => setData((current) => ({ ...current, [key]: value })), []);

    return { data, status, reload, setLocal };
}
