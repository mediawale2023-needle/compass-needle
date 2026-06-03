'use client';
import { useState, useEffect } from 'react';
import { apiGet } from '@/lib/api';

const STATUS_STYLES = {
    active:   { badgeClass: 'badge badge-green badge-dot', dotColor: '#10b981', label: 'Active' },
    stale:    { badgeClass: 'badge badge-amber badge-dot', dotColor: '#f59e0b', label: 'Stale' },
    inactive: { badgeClass: 'badge badge-red badge-dot',  dotColor: '#f43f5e', label: 'Inactive' },
    no_data:  { badgeClass: 'badge badge-slate badge-dot', dotColor: '#94a3b8', label: 'No Data' },
};

const SUMMARY_COLORS = {
    active:   { accent: '#10b981', bg: '#ecfdf5' },
    stale:    { accent: '#f59e0b', bg: '#fffbeb' },
    inactive: { accent: '#f43f5e', bg: '#fff1f2' },
    no_data:  { accent: '#94a3b8', bg: '#f8fafc' },
};

export default function TenantHealthPage() {
    const [tenants, setTenants] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        apiGet('/api/admin/tenant-health')
            .then(d => setTenants(d.tenants || []))
            .catch(e => setError(e.message || 'Failed to load'))
            .finally(() => setLoading(false));
    }, []);

    const normalizedTenants = tenants.map(t => ({
        tenant_id: t.tenant_id ?? t.id,
        mp_name: t.mp_name ?? t.name,
        constituency: t.constituency,
        status: t.status ?? t.health ?? 'no_data',
        last_case_at: t.last_case_at ?? t.last_case,
        last_login_at: t.last_login_at ?? t.last_login,
        cases_last_30d: t.cases_last_30d ?? t.total_cases,
        total_cases: t.total_cases,
        open_cases: t.open_cases,
    }));

    const counts = { active: 0, stale: 0, inactive: 0, no_data: 0 };
    normalizedTenants.forEach(t => { if (counts[t.status] !== undefined) counts[t.status]++; });

    return (
        <>
            {/* Summary Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: '1.5rem' }}>
                {Object.entries(STATUS_STYLES).map(([key, s]) => {
                    const c = SUMMARY_COLORS[key];
                    return (
                        <div key={key} className="stat-card" style={{ borderLeft: `3px solid ${c.accent}` }}>
                            <div style={{ fontSize: '1.9rem', fontWeight: 800, color: c.accent, lineHeight: 1, letterSpacing: '-1px' }}>
                                {counts[key]}
                            </div>
                            <div style={{ color: '#6b7f76', fontSize: '0.72rem', fontWeight: 500, marginTop: 5, textTransform: 'uppercase', letterSpacing: '0.7px' }}>
                                {s.label}
                            </div>
                        </div>
                    );
                })}
            </div>

            {error && <div className="toast toast-error" style={{ marginBottom: '1rem' }}>{error}</div>}

            {loading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {[...Array(5)].map((_, i) => <div key={i} className="skeleton" style={{ height: 48, borderRadius: 8 }} />)}
                </div>
            ) : normalizedTenants.length === 0 ? (
                <div className="glass-panel">
                    <div className="empty-state">
                        <div className="empty-state-title">No tenant data available</div>
                        <div className="empty-state-desc">Tenant health data will appear once MPs are active</div>
                    </div>
                </div>
            ) : (
                <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>MP / Tenant</th>
                                <th>Constituency</th>
                                <th>Status</th>
                                <th>Last Case</th>
                                <th>Last Login</th>
                                <th style={{ textAlign: 'right' }}>Cases (30d)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {normalizedTenants.map((t) => {
                                const s = STATUS_STYLES[t.status] || STATUS_STYLES.no_data;
                                return (
                                    <tr key={t.tenant_id}>
                                        <td style={{ fontWeight: 600 }}>
                                            {t.mp_name || `Tenant #${t.tenant_id}`}
                                            <div style={{ marginTop: 2, fontSize: '0.7rem', color: '#94a3a0', fontWeight: 500 }}>
                                                Tenant #{t.tenant_id}
                                            </div>
                                        </td>
                                        <td style={{ color: '#6b7f76' }}>{t.constituency || '—'}</td>
                                        <td>
                                            <span className={s.badgeClass}>{s.label}</span>
                                        </td>
                                        <td style={{ color: '#6b7f76', fontSize: '0.8rem' }}>
                                            {t.last_case_at ? new Date(t.last_case_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                                        </td>
                                        <td style={{ color: '#6b7f76', fontSize: '0.8rem' }}>
                                            {t.last_login_at ? new Date(t.last_login_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                                        </td>
                                        <td style={{ textAlign: 'right', fontWeight: 700, color: '#1a2e28' }}>
                                            {t.cases_last_30d ?? '—'}
                                            <div style={{ marginTop: 2, fontSize: '0.68rem', color: '#94a3a0', fontWeight: 500 }}>
                                                {t.open_cases ?? 0} open / {t.total_cases ?? 0} total
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </>
    );
}
