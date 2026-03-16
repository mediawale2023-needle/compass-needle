'use client';
import { useState, useEffect } from 'react';
import { apiGet } from '@/lib/api';

const STATUS_STYLES = {
    active:   { bg: '#ecfdf5', color: '#065f46', dot: '#10b981', label: 'Active' },
    stale:    { bg: '#fffbeb', color: '#92400e', dot: '#f59e0b', label: 'Stale' },
    inactive: { bg: '#fff1f2', color: '#9f1239', dot: '#f43f5e', label: 'Inactive' },
    no_data:  { bg: '#f8fafc', color: '#64748b', dot: '#94a3b8', label: 'No Data' },
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

    const counts = { active: 0, stale: 0, inactive: 0, no_data: 0 };
    tenants.forEach(t => { if (counts[t.status] !== undefined) counts[t.status]++; });

    return (
        <>
            <div className="section-title">Tenant Health</div>
            <p style={{ color: '#6b7f76', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
                Monitor MP tenant activity status across the platform.
            </p>

            {/* Summary row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: '1.5rem' }}>
                {Object.entries(STATUS_STYLES).map(([key, s]) => (
                    <div key={key} className="stat-card" style={{ borderLeft: `4px solid ${s.dot}` }}>
                        <div style={{ fontSize: '1.8rem', fontWeight: 800, color: s.dot, lineHeight: 1 }}>
                            {counts[key]}
                        </div>
                        <div style={{ color: '#6b7f76', fontSize: '0.75rem', fontWeight: 500, marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.8px' }}>
                            {s.label}
                        </div>
                    </div>
                ))}
            </div>

            {error && (
                <div style={{ padding: '12px 16px', background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: 8, color: '#be123c', marginBottom: '1rem', fontSize: '0.85rem' }}>
                    {error}
                </div>
            )}

            {loading ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7f76' }}>Loading…</div>
            ) : tenants.length === 0 ? (
                <div className="glass-panel" style={{ textAlign: 'center', color: '#6b7f76', padding: '2rem' }}>
                    No tenant data available.
                </div>
            ) : (
                <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                        <thead>
                            <tr style={{ background: '#f0f7f4', borderBottom: '1px solid #e2ebe5' }}>
                                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#1a2e28' }}>MP / Tenant</th>
                                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#1a2e28' }}>Constituency</th>
                                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#1a2e28' }}>Status</th>
                                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#1a2e28' }}>Last Case</th>
                                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#1a2e28' }}>Last Login</th>
                                <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#1a2e28' }}>Cases (30d)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {tenants.map((t, i) => {
                                const s = STATUS_STYLES[t.status] || STATUS_STYLES.no_data;
                                return (
                                    <tr key={t.tenant_id} style={{ borderBottom: i < tenants.length - 1 ? '1px solid #e2ebe5' : 'none' }}>
                                        <td style={{ padding: '12px 16px', fontWeight: 600, color: '#1a2e28' }}>
                                            {t.mp_name || `Tenant #${t.tenant_id}`}
                                        </td>
                                        <td style={{ padding: '12px 16px', color: '#6b7f76' }}>
                                            {t.constituency || '—'}
                                        </td>
                                        <td style={{ padding: '12px 16px' }}>
                                            <span style={{
                                                display: 'inline-flex', alignItems: 'center', gap: 6,
                                                padding: '3px 10px', borderRadius: 20,
                                                background: s.bg, color: s.color,
                                                fontSize: '0.75rem', fontWeight: 600,
                                            }}>
                                                <span style={{ width: 6, height: 6, borderRadius: '50%', background: s.dot, display: 'inline-block' }} />
                                                {s.label}
                                            </span>
                                        </td>
                                        <td style={{ padding: '12px 16px', color: '#6b7f76', fontSize: '0.8rem' }}>
                                            {t.last_case_at ? new Date(t.last_case_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                                        </td>
                                        <td style={{ padding: '12px 16px', color: '#6b7f76', fontSize: '0.8rem' }}>
                                            {t.last_login_at ? new Date(t.last_login_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                                        </td>
                                        <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#1a2e28' }}>
                                            {t.cases_last_30d ?? '—'}
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
