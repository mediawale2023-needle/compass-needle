'use client';
import { useState, useEffect } from 'react';
import { apiGet } from '@/lib/api';

const METRIC_DEFS = [
    { key: 'cases',     label: 'Cases',     accent: '#0891b2' },
    { key: 'letters',   label: 'Letters',   accent: '#006a4d' },
    { key: 'questions', label: 'PQs',       accent: '#7c3aed' },
    { key: 'docs',      label: 'Analyses',  accent: '#d97706' },
    { key: 'letterbox', label: 'Letterbox', accent: '#e11d48' },
];

export default function UsageAnalyticsPage() {
    const [rows, setRows] = useState([]);
    const [period, setPeriod] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        apiGet('/api/admin/usage-analytics')
            .then(d => {
                setRows(d.tenants || []);
                setPeriod(d.period || '');
            })
            .catch(e => setError(e.message || 'Failed to load'))
            .finally(() => setLoading(false));
    }, []);

    const normalizedRows = rows.map(r => ({
        tenant_id: r.tenant_id,
        mp_name: r.mp_name ?? r.name,
        constituency: r.constituency,
        cases: r.cases ?? r.cases_this_month ?? 0,
        cases_total: r.cases_total ?? 0,
        letters: r.letters ?? r.letters_drafted ?? 0,
        questions: r.questions ?? r.questions_drafted ?? 0,
        docs: r.docs ?? r.docs_analysed ?? 0,
        letterbox: r.letterbox ?? r.letterbox_items ?? 0,
    }));

    const totals = normalizedRows.reduce((acc, r) => ({
        cases:     acc.cases     + (r.cases     || 0),
        letters:   acc.letters   + (r.letters   || 0),
        questions: acc.questions + (r.questions || 0),
        docs:      acc.docs      + (r.docs      || 0),
        letterbox: acc.letterbox + (r.letterbox || 0),
    }), { cases: 0, letters: 0, questions: 0, docs: 0, letterbox: 0 });

    return (
        <>
            {/* Summary Cards */}
            {period && (
                <div style={{ marginBottom: 12, color: '#6b7f76', fontSize: '0.8rem', fontWeight: 600 }}>
                    Current period: <span style={{ color: '#1a2e28' }}>{period}</span>
                </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: '1.5rem' }}>
                {METRIC_DEFS.map(m => (
                    <div key={m.key} className="stat-card">
                        <div style={{ fontSize: '1.8rem', fontWeight: 800, color: m.accent, lineHeight: 1, letterSpacing: '-1px' }}>
                            {totals[m.key]}
                        </div>
                        <div style={{ color: '#6b7f76', fontSize: '0.72rem', fontWeight: 500, marginTop: 5, textTransform: 'uppercase', letterSpacing: '0.7px' }}>
                            {m.label}
                        </div>
                    </div>
                ))}
            </div>

            {error && <div className="toast toast-error">{error}</div>}

            {loading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {[...Array(6)].map((_, i) => <div key={i} className="skeleton" style={{ height: 48, borderRadius: 8 }} />)}
                </div>
            ) : normalizedRows.length === 0 ? (
                <div className="glass-panel">
                    <div className="empty-state">
                        <div className="empty-state-title">No usage data available</div>
                        <div className="empty-state-desc">Activity data will appear as MPs use the platform</div>
                    </div>
                </div>
            ) : (
                <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>MP / Tenant</th>
                                {METRIC_DEFS.map(m => <th key={m.key} style={{ textAlign: 'right' }}>{m.label}</th>)}
                                <th style={{ textAlign: 'right' }}>Cases Total</th>
                                <th style={{ textAlign: 'right' }}>Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            {normalizedRows.map((r) => {
                                const total = METRIC_DEFS.reduce((sum, m) => sum + (r[m.key] || 0), 0);
                                return (
                                    <tr key={r.tenant_id}>
                                        <td>
                                            <div style={{ fontWeight: 600, color: '#1a2e28' }}>
                                                {r.mp_name || `Tenant #${r.tenant_id}`}
                                            </div>
                                            {r.constituency && (
                                                <div style={{ fontSize: '0.72rem', color: '#6b7f76', marginTop: 1 }}>{r.constituency}</div>
                                            )}
                                            <div style={{ fontSize: '0.68rem', color: '#94a3a0', marginTop: 1 }}>Tenant #{r.tenant_id}</div>
                                        </td>
                                        {METRIC_DEFS.map(m => (
                                            <td key={m.key} style={{ textAlign: 'right', fontWeight: 600, color: r[m.key] ? m.accent : '#d1d5db' }}>
                                                {r[m.key] || 0}
                                            </td>
                                        ))}
                                        <td style={{ textAlign: 'right', fontWeight: 700, color: '#6b7f76' }}>{r.cases_total || 0}</td>
                                        <td style={{ textAlign: 'right', fontWeight: 700, color: '#1a2e28', fontSize: '0.9rem' }}>{total}</td>
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
