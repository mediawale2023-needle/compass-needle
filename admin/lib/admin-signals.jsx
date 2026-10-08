'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { apiGet } from '@/lib/api';
import { navSignals, platformCondition } from '@/lib/admin-data';

/**
 * One shared /api/admin/alerts subscription for the whole shell (sidebar
 * counts, footer condition, notifications) instead of each widget polling.
 * `alerts` is null until the first successful load; on failure it stays
 * null so nothing claims "healthy" without evidence.
 */
const AdminSignalsContext = createContext({
    alerts: null,
    status: 'idle',
    refresh: () => {},
    signals: {},
    condition: null,
    reportAttention: () => {},
});

const POLL_MS = 5 * 60 * 1000;

export function AdminSignalsProvider({ children, pollMs = POLL_MS }) {
    const [alerts, setAlerts] = useState(null);
    const [status, setStatus] = useState('idle');
    // The Command Centre derives the precise attention queue (alerts merged
    // with WhatsApp health). While it is mounted it reports those counts so
    // the sidebar shows the same number as the page instead of a raw-alert
    // count from a different definition.
    const [attention, setAttention] = useState(null);
    const reportAttention = useCallback((counts) => setAttention(counts || null), []);

    const refresh = useCallback(async () => {
        setStatus((current) => (current === 'ready' ? 'refreshing' : 'loading'));
        try {
            const data = await apiGet('/api/admin/alerts');
            setAlerts(Array.isArray(data?.alerts) ? data.alerts : []);
            setStatus('ready');
        } catch {
            setStatus('error');
        }
    }, []);

    useEffect(() => {
        refresh();
        if (!pollMs) return undefined;
        const timer = setInterval(refresh, pollMs);
        return () => clearInterval(timer);
    }, [refresh, pollMs]);

    const value = useMemo(() => {
        const signals = navSignals(alerts);
        if (attention) {
            const actionable = (attention.critical || 0) + (attention.warning || 0);
            if (actionable) signals.command = { count: actionable, severity: attention.critical ? 'critical' : 'warning' };
            else delete signals.command;
        }
        return { alerts, status, refresh, signals, condition: platformCondition(alerts), reportAttention };
    }, [alerts, status, refresh, attention, reportAttention]);

    return <AdminSignalsContext.Provider value={value}>{children}</AdminSignalsContext.Provider>;
}

export function useAdminSignals() {
    return useContext(AdminSignalsContext);
}
