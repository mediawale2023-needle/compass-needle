'use client';
import { useState, useEffect } from 'react';
import { apiGet } from '@/lib/api';

export default function CaseIntelligencePage() {
    const [view, setView] = useState('health');

    return (
        <>
            <div className="tab-list">
                {[
                    { key: 'health', label: 'Platform Health' },
                    { key: 'explorer', label: 'Case Explorer' },
                    { key: 'analytics', label: 'Grievance Analytics' },
                ].map(v => (
                    <button key={v.key} className={`tab-item${view === v.key ? ' active' : ''}`} onClick={() => setView(v.key)}>
                        {v.label}
                    </button>
                ))}
            </div>

            {view === 'health' && <PlatformHealth />}
            {view === 'explorer' && <CaseExplorer />}
            {view === 'analytics' && <GrievanceAnalytics />}
        </>
    );
}

/* ═══ Platform Health ═══ */
function PlatformHealth() {
    const [data, setData] = useState(null);
    useEffect(() => { apiGet('/api/admin/cases/health').then(setData).catch(() => { }); }, []);

    if (!data) return <LoadingGrid count={4} />;

    const maxStatus = Math.max(...(data.status_breakdown?.map(x => x.count) || [1]), 1);
    const maxMp = Math.max(...(data.mp_cases?.map(x => x.cases) || [1]), 1);
    const maxVol = Math.max(...(data.volume_30d?.map(x => x.count) || [1]), 1);

    return (
        <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: '1.5rem' }}>
                <MetricCard value={data.total_cases?.toLocaleString()} label="Total Cases" accent="#006a4d" bg="#f0fdf4" />
                <MetricCard value={data.active_mps} label="Active MPs" accent="#2563eb" bg="#eff6ff" />
                <MetricCard value={data.resolved?.toLocaleString()} label="Resolved" accent="#059669" bg="#f0fdf4" />
                <MetricCard value={data.critical} label="Critical" accent="#dc2626" bg="#fff1f2" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: '1.5rem' }}>
                <div className="glass-panel">
                    <div style={{ fontWeight: 600, color: '#1a2e28', fontSize: '0.9rem', marginBottom: 14 }}>Cases by Status</div>
                    {data.status_breakdown?.length > 0 ? data.status_breakdown.map(s => (
                        <div key={s.status} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                            <div style={{ width: 90, fontSize: '0.78rem', fontWeight: 500, color: '#4a635a', flexShrink: 0 }}>{s.status}</div>
                            <div className="bar-track">
                                <div className="bar-fill" style={{ width: `${(s.count / maxStatus) * 100}%`, background: 'linear-gradient(90deg, #006a4d, #059669)' }}>
                                    {s.count}
                                </div>
                            </div>
                        </div>
                    )) : <EmptyMsg />}
                </div>
                <div className="glass-panel">
                    <div style={{ fontWeight: 600, color: '#1a2e28', fontSize: '0.9rem', marginBottom: 14 }}>Cases per MP (Top 10)</div>
                    {data.mp_cases?.length > 0 ? data.mp_cases.slice(0, 10).map(m => (
                        <div key={m.name} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                            <div style={{ width: 110, fontSize: '0.78rem', fontWeight: 500, color: '#4a635a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flexShrink: 0 }}>{m.name}</div>
                            <div className="bar-track">
                                <div className="bar-fill" style={{ width: `${(m.cases / maxMp) * 100}%`, background: 'linear-gradient(90deg, #0891b2, #06b6d4)' }}>
                                    {m.cases}
                                </div>
                            </div>
                        </div>
                    )) : <EmptyMsg />}
                </div>
            </div>

            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                <div style={{ fontWeight: 600, color: '#1a2e28', fontSize: '0.9rem', marginBottom: 14 }}>MP Activity</div>
                {data.activity?.length > 0 ? (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>MP</th><th>Constituency</th><th>Cases</th><th>Last Login</th><th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.activity.map((a, i) => (
                                <tr key={i}>
                                    <td style={{ fontWeight: 600 }}>{a.mp}</td>
                                    <td style={{ color: '#6b7f76' }}>{a.constituency}</td>
                                    <td style={{ fontWeight: 600 }}>{a.cases}</td>
                                    <td style={{ color: '#6b7f76', fontSize: '0.8rem' }}>{a.last_login}</td>
                                    <td>
                                        <span className={`badge badge-dot ${a.active ? 'badge-green' : 'badge-slate'}`}>
                                            {a.active ? 'Active' : 'Never logged in'}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : <EmptyMsg />}
            </div>

            <div className="glass-panel">
                <div style={{ fontWeight: 600, color: '#1a2e28', fontSize: '0.9rem', marginBottom: 14 }}>Case Volume — Last 30 Days</div>
                {data.volume_30d?.length > 0 ? (
                    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 100 }}>
                        {data.volume_30d.map((v, i) => (
                            <div key={i} title={`${v.day}: ${v.count} cases`} style={{
                                flex: 1,
                                background: `linear-gradient(180deg, #006a4d, #059669)`,
                                borderRadius: '3px 3px 0 0',
                                height: `${Math.max(2, (v.count / maxVol) * 100)}%`,
                                cursor: 'pointer',
                                transition: 'opacity 0.15s',
                                opacity: 0.85,
                            }}
                                onMouseEnter={e => e.currentTarget.style.opacity = '1'}
                                onMouseLeave={e => e.currentTarget.style.opacity = '0.85'}
                            />
                        ))}
                    </div>
                ) : <EmptyMsg />}
            </div>
        </>
    );
}

/* ═══ Case Explorer ═══ */
function CaseExplorer() {
    const [data, setData] = useState(null);
    const [filters, setFilters] = useState({ mp_id: '', period: '', category: '', status: '' });
    const [caseId, setCaseId] = useState('');
    const [detail, setDetail] = useState(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);

    const fetchCases = () => {
        setLoading(true);
        setError('');
        const params = new URLSearchParams();
        Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
        const qs = params.toString();
        apiGet(`/api/admin/cases/explorer${qs ? '?' + qs : ''}`)
            .then(d => { setData(d); setLoading(false); })
            .catch(e => { setError(e.message || 'Failed to load cases'); setLoading(false); });
    };

    useEffect(() => { fetchCases(); }, [filters]);

    const loadDetail = () => {
        if (!caseId) return;
        apiGet(`/api/admin/cases/${caseId}`).then(setDetail).catch(() => setDetail(null));
    };

    return (
        <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: '1rem' }}>
                {[
                    { key: 'mp_id', label: 'MP', options: data?.filter_options?.mps?.map(m => ({ value: m.id, label: `${m.name} (${m.constituency})` })) },
                    { key: 'period', label: 'Period', options: [{ value: '7days', label: 'Last 7 Days' }, { value: '30days', label: 'Last 30 Days' }, { value: '90days', label: 'Last 90 Days' }] },
                    { key: 'category', label: 'Category', options: data?.filter_options?.categories?.map(c => ({ value: c, label: c })) },
                    { key: 'status', label: 'Status', options: data?.filter_options?.statuses?.map(s => ({ value: s, label: s })) },
                ].map(f => (
                    <div key={f.key}>
                        <label className="form-label">{f.label}</label>
                        <select className="form-input" value={filters[f.key]} onChange={e => setFilters({ ...filters, [f.key]: e.target.value })}>
                            <option value="">All</option>
                            {(f.options || []).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                    </div>
                ))}
            </div>

            {/* Error banner */}
            {error && (
                <div className="toast toast-error" style={{ position: 'relative', marginBottom: 12 }}>
                    API Error: {error}
                    <button onClick={fetchCases} style={{ marginLeft: 12, background: 'white', border: '1px solid #fca5a5', borderRadius: 6, padding: '2px 10px', fontSize: '0.74rem', cursor: 'pointer', color: '#be123c', fontWeight: 600 }}>
                        Retry
                    </button>
                </div>
            )}

            {/* Loading */}
            {loading && !data && <LoadingGrid count={1} />}

            {data && (
                <div style={{ color: '#6b7f76', fontSize: '0.76rem', marginBottom: 10 }}>
                    Showing {Math.min(data.total, 200)} of <strong>{data.total?.toLocaleString()}</strong> cases
                </div>
            )}

            {data?.cases?.length > 0 ? (
                <div className="glass-panel" style={{ overflow: 'auto', marginBottom: '1.5rem', padding: 0 }}>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>ID</th><th>MP</th><th>Contact</th><th>Category</th><th>Status</th>
                                <th>Location</th><th>Assembly</th><th>Message</th><th>Created</th><th>!</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.cases.map(c => (
                                <tr key={c.id}>
                                    <td style={{ fontWeight: 600, color: '#006a4d' }}>#{c.id}</td>
                                    <td style={{ fontWeight: 500 }}>{c.mp}</td>
                                    <td style={{ color: '#6b7f76', fontSize: '0.8rem' }}>{c.phone}</td>
                                    <td>{c.category}</td>
                                    <td>
                                        <span className={`badge ${c.status === 'resolved' ? 'badge-green' : c.status === 'in_progress' ? 'badge-amber' : 'badge-slate'}`}>
                                            {c.status}
                                        </span>
                                    </td>
                                    <td style={{ color: '#6b7f76' }}>{c.location}</td>
                                    <td style={{ color: '#6b7f76' }}>{c.assembly}</td>
                                    <td style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#6b7f76', fontSize: '0.8rem' }}>{c.message}</td>
                                    <td style={{ fontSize: '0.78rem', color: '#6b7f76' }}>{c.created}</td>
                                    <td>{c.critical ? <span style={{ color: '#dc2626', fontSize: '0.75rem', fontWeight: 700 }}>●</span> : ''}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            ) : (
                <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                    <div className="empty-state">
                        <div className="empty-state-title">No cases match the selected filters</div>
                        <div className="empty-state-desc">Try adjusting the filters above</div>
                    </div>
                </div>
            )}

            <div className="glass-panel">
                <div style={{ fontWeight: 600, color: '#1a2e28', fontSize: '0.9rem', marginBottom: 12 }}>Case Detail Lookup</div>
                <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                    <input className="form-input" type="number" min={1} placeholder="Enter Case ID" value={caseId} onChange={e => setCaseId(e.target.value)} style={{ flex: 1 }} />
                    <button className="btn-primary" onClick={loadDetail}>Lookup</button>
                </div>
                {detail && (
                    <div style={{ border: '1px solid #e2ebe5', borderRadius: 10, padding: '1.25rem' }}>
                        <div style={{ fontWeight: 700, color: '#1a2e28', marginBottom: 14, fontSize: '0.9rem' }}>Case #{detail.id}</div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 16 }}>
                            {[
                                ['MP', detail.mp_name], ['Constituency', detail.mp_constituency], ['Phone', detail.phone],
                                ['Category', detail.category], ['Status', detail.status], ['Critical', detail.critical ? 'Yes' : 'No'],
                                ['Location', detail.location], ['Assembly', detail.assembly], ['Confidence', detail.confidence],
                            ].map(([l, v]) => (
                                <div key={l}>
                                    <div className="form-label">{l}</div>
                                    <div style={{ fontSize: '0.85rem', color: '#1a2e28', fontWeight: 500 }}>{v || '—'}</div>
                                </div>
                            ))}
                        </div>
                        <hr className="divider" />
                        <div className="form-label" style={{ marginBottom: 6 }}>Full Message</div>
                        <pre style={{ background: '#f8faf9', padding: '10px 14px', borderRadius: 8, fontSize: '0.8rem', whiteSpace: 'pre-wrap', marginBottom: 12, color: '#1a2e28', border: '1px solid #e2ebe5' }}>{detail.raw_message}</pre>
                        {detail.response_to_citizen && (
                            <>
                                <div className="form-label" style={{ marginBottom: 6 }}>AI Response to Citizen</div>
                                <pre style={{ background: '#f0fdf4', padding: '10px 14px', borderRadius: 8, fontSize: '0.8rem', whiteSpace: 'pre-wrap', marginBottom: 12, color: '#1a2e28', border: '1px solid #bbf7d0' }}>{detail.response_to_citizen}</pre>
                            </>
                        )}
                        {detail.notes_for_staff && (
                            <>
                                <div className="form-label" style={{ marginBottom: 6 }}>Staff Notes</div>
                                <pre style={{ background: '#fffbeb', padding: '10px 14px', borderRadius: 8, fontSize: '0.8rem', whiteSpace: 'pre-wrap', marginBottom: 12, color: '#1a2e28', border: '1px solid #fef08a' }}>{detail.notes_for_staff}</pre>
                            </>
                        )}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, color: '#6b7f76', fontSize: '0.74rem' }}>
                            <div>Created: {detail.created_at}</div>
                            <div>Updated: {detail.updated_at}</div>
                            <div>Resolved: {detail.resolved_at || '—'}</div>
                        </div>
                    </div>
                )}
            </div>
        </>
    );
}

/* ═══ Grievance Analytics ═══ */
function GrievanceAnalytics() {
    const [data, setData] = useState(null);
    useEffect(() => { apiGet('/api/admin/cases/analytics/data').then(setData).catch(() => { }); }, []);
    if (!data) return <LoadingGrid count={3} />;

    const maxCat = Math.max(...(data.category_breakdown?.map(x => x.count) || [1]), 1);
    const maxAsm = Math.max(...(data.assembly_distribution?.map(x => x.cases) || [1]), 1);

    return (
        <>
            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                <div style={{ fontWeight: 600, color: '#1a2e28', fontSize: '0.9rem', marginBottom: 14 }}>Most Common Grievance Categories</div>
                {data.category_breakdown?.length > 0 ? data.category_breakdown.slice(0, 12).map((c, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 7 }}>
                        <div style={{ width: 130, fontSize: '0.79rem', fontWeight: 500, color: '#4a635a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flexShrink: 0 }}>{c.category}</div>
                        <div style={{ width: 90, fontSize: '0.72rem', color: '#6b7f76', flexShrink: 0 }}>{c.constituency}</div>
                        <div className="bar-track">
                            <div className="bar-fill" style={{ width: `${(c.count / maxCat) * 100}%`, background: 'linear-gradient(90deg, #d97706, #f59e0b)' }}>
                                {c.count}
                            </div>
                        </div>
                    </div>
                )) : <EmptyMsg />}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: '1.5rem' }}>
                <div className="glass-panel">
                    <div style={{ fontWeight: 600, color: '#1a2e28', fontSize: '0.9rem', marginBottom: 14 }}>Category Volume (All MPs)</div>
                    {data.category_volume?.length > 0 ? (
                        <table className="data-table">
                            <thead><tr><th>Category</th><th>Count</th></tr></thead>
                            <tbody>
                                {data.category_volume.map(c => (
                                    <tr key={c.category}>
                                        <td>{c.category}</td>
                                        <td style={{ fontWeight: 600 }}>{c.count}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    ) : <EmptyMsg />}
                </div>
                <div className="glass-panel">
                    <div style={{ fontWeight: 600, color: '#1a2e28', fontSize: '0.9rem', marginBottom: 14 }}>Status Distribution</div>
                    {data.status_distribution?.length > 0 ? (
                        <table className="data-table">
                            <thead><tr><th>Status</th><th>Count</th></tr></thead>
                            <tbody>
                                {data.status_distribution.map(s => (
                                    <tr key={s.status}>
                                        <td>
                                            <span className={`badge ${s.status === 'resolved' ? 'badge-green' : s.status === 'in_progress' ? 'badge-amber' : 'badge-slate'}`}>
                                                {s.status}
                                            </span>
                                        </td>
                                        <td style={{ fontWeight: 600 }}>{s.count}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    ) : <EmptyMsg />}
                </div>
            </div>

            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                <div style={{ fontWeight: 600, color: '#1a2e28', fontSize: '0.9rem', marginBottom: 14 }}>Average Resolution Time</div>
                {data.resolution_times?.length > 0 ? (
                    <table className="data-table">
                        <thead><tr><th>MP</th><th>Constituency</th><th>Resolved Cases</th><th>Avg Time</th></tr></thead>
                        <tbody>
                            {data.resolution_times.map((r, i) => (
                                <tr key={i}>
                                    <td style={{ fontWeight: 500 }}>{r.mp}</td>
                                    <td style={{ color: '#6b7f76' }}>{r.constituency}</td>
                                    <td style={{ fontWeight: 600 }}>{r.resolved_cases}</td>
                                    <td style={{ color: '#6b7f76' }}>{r.avg_resolution_time}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : <EmptyMsg text="No resolution data available yet." />}
            </div>

            <div className="glass-panel">
                <div style={{ fontWeight: 600, color: '#1a2e28', fontSize: '0.9rem', marginBottom: 14 }}>Cases by Assembly Constituency</div>
                {data.assembly_distribution?.length > 0 ? data.assembly_distribution.slice(0, 15).map((a, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 7 }}>
                        <div style={{ width: 150, fontSize: '0.79rem', fontWeight: 500, color: '#4a635a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flexShrink: 0 }}>{a.assembly}</div>
                        <div className="bar-track">
                            <div className="bar-fill" style={{ width: `${(a.cases / maxAsm) * 100}%`, background: 'linear-gradient(90deg, #8d153a, #b91c50)' }}>
                                {a.cases}
                            </div>
                        </div>
                    </div>
                )) : <EmptyMsg />}
            </div>
        </>
    );
}

/* ═══ Shared sub-components ═══ */
function MetricCard({ value, label, accent, bg }) {
    return (
        <div className="stat-card" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '2rem', fontWeight: 800, color: accent, lineHeight: 1, letterSpacing: '-1.5px' }}>{value ?? '—'}</div>
            <div style={{ fontSize: '0.72rem', color: '#6b7f76', marginTop: 6, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.7px' }}>{label}</div>
        </div>
    );
}

function EmptyMsg({ text = 'No data available.' }) {
    return <div style={{ color: '#6b7f76', fontSize: '0.82rem', padding: '0.5rem 0' }}>{text}</div>;
}

function LoadingGrid({ count = 4 }) {
    return (
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${count}, 1fr)`, gap: 12, marginBottom: '1.5rem' }}>
            {[...Array(count)].map((_, i) => <div key={i} className="stat-card skeleton" style={{ height: 80 }} />)}
        </div>
    );
}
