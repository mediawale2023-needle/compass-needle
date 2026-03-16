'use client';
import { useState, useEffect } from 'react';
import { apiGet } from '@/lib/api';

export default function UsageAnalyticsPage() {
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        apiGet('/api/admin/usage-analytics')
            .then(d => setRows(d.tenants || []))
            .catch(e => setError(e.message || 'Failed to load'))
            .finally(() => setLoading(false));
    }, []);

    const totals = rows.reduce((acc, r) => ({
        cases: acc.cases + (r.cases || 0),
        letters: acc.letters + (r.letters || 0),
        questions: acc.questions + (r.questions || 0),
        docs: acc.docs + (r.docs || 0),
        letterbox: acc.letterbox + (r.letterbox || 0),
    }), { cases: 0, letters: 0, questions: 0, docs: 0, letterbox: 0 });

    return (
        <>
            <div className="section-title">Usage Analytics</div>
            <p style={{ color: '#6b7f76', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
                Monthly activity per tenant (current calendar month).
            </p>

            {/* Summary */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: '1.5rem' }}>
                {[
                    { label: 'Cases', value: totals.cases, icon: '📩', color: '#0891b2' },
                    { label: 'Letters', value: totals.letters, icon: '✉️', color: '#006a4d' },
                    { label: 'Questions', value: totals.questions, icon: '❓', color: '#7c3aed' },
                    { label: 'Analyses', value: totals.docs, icon: '🔍', color: '#d97706' },
                    { label: 'Letterbox', value: totals.letterbox, icon: '📬', color: '#e11d48' },
                ].map(s => (
                    <div key={s.label} className="stat-card">
                        <div style={{ fontSize: '1.2rem', marginBottom: 4 }}>{s.icon}</div>
                        <div style={{ fontSize: '1.8rem', fontWeight: 800, color: s.color, lineHeight: 1 }}>{s.value}</div>
                        <div style={{ color: '#6b7f76', fontSize: '0.75rem', fontWeight: 500, marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.8px' }}>{s.label}</div>
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
            ) : rows.length === 0 ? (
                <div className="glass-panel" style={{ textAlign: 'center', color: '#6b7f76', padding: '2rem' }}>
                    No data available.
                </div>
            ) : (
                <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                        <thead>
                            <tr style={{ background: '#f0f7f4', borderBottom: '1px solid #e2ebe5' }}>
                                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#1a2e28' }}>MP / Tenant</th>
                                <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#1a2e28' }}>Cases</th>
                                <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#1a2e28' }}>Letters</th>
                                <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#1a2e28' }}>PQs</th>
                                <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#1a2e28' }}>Analyses</th>
                                <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#1a2e28' }}>Letterbox</th>
                                <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#1a2e28' }}>Total Activity</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((r, i) => {
                                const total = (r.cases || 0) + (r.letters || 0) + (r.questions || 0) + (r.docs || 0) + (r.letterbox || 0);
                                return (
                                    <tr key={r.tenant_id} style={{ borderBottom: i < rows.length - 1 ? '1px solid #e2ebe5' : 'none' }}>
                                        <td style={{ padding: '12px 16px', fontWeight: 600, color: '#1a2e28' }}>
                                            {r.mp_name || `Tenant #${r.tenant_id}`}
                                            {r.constituency && (
                                                <div style={{ fontSize: '0.75rem', color: '#6b7f76', fontWeight: 400 }}>{r.constituency}</div>
                                            )}
                                        </td>
                                        <td style={{ padding: '12px 16px', textAlign: 'right', color: '#0891b2', fontWeight: 600 }}>{r.cases || 0}</td>
                                        <td style={{ padding: '12px 16px', textAlign: 'right', color: '#006a4d', fontWeight: 600 }}>{r.letters || 0}</td>
                                        <td style={{ padding: '12px 16px', textAlign: 'right', color: '#7c3aed', fontWeight: 600 }}>{r.questions || 0}</td>
                                        <td style={{ padding: '12px 16px', textAlign: 'right', color: '#d97706', fontWeight: 600 }}>{r.docs || 0}</td>
                                        <td style={{ padding: '12px 16px', textAlign: 'right', color: '#e11d48', fontWeight: 600 }}>{r.letterbox || 0}</td>
                                        <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 700, color: '#1a2e28' }}>{total}</td>
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
