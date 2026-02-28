'use client';
import { useState, useEffect } from 'react';
import { apiGet } from '@/lib/api';

export default function CaseIntelligencePage() {
    const [view, setView] = useState('health');

    return (
        <>
            {/* View Selector */}
            <div className="tab-list" style={{ marginBottom: '1.5rem' }}>
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
    if (!data) return <div style={{ color: '#6b7f76', padding: '2rem', textAlign: 'center' }}>Loading...</div>;

    return (
        <>
            <div className="section-title">Platform Health</div>
            {/* Metric Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: '1.5rem' }}>
                <MetricCard icon="📊" value={data.total_cases?.toLocaleString()} label="Total Cases" />
                <MetricCard icon="👥" value={data.active_mps} label="Active MPs" />
                <MetricCard icon="✅" value={data.resolved?.toLocaleString()} label="Resolved" />
                <MetricCard icon="🔴" value={data.critical} label="Critical" />
            </div>

            {/* Cases by Status */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: '1.5rem' }}>
                <div className="glass-panel">
                    <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Cases by Status</h3>
                    {data.status_breakdown?.length > 0 ? (
                        <div>
                            {data.status_breakdown.map(s => (
                                <div key={s.status} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                                    <div style={{ width: 100, fontSize: '0.82rem', fontWeight: 500, color: '#4a635a' }}>{s.status}</div>
                                    <div style={{ flex: 1, background: '#e8efe9', borderRadius: 4, height: 22, overflow: 'hidden' }}>
                                        <div style={{
                                            width: `${Math.min(100, (s.count / Math.max(...data.status_breakdown.map(x => x.count))) * 100)}%`,
                                            height: '100%', background: 'linear-gradient(90deg, #006a4d, #059669)', borderRadius: 4,
                                            display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: 6,
                                            fontSize: '0.7rem', color: 'white', fontWeight: 600,
                                        }}>{s.count}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : <div style={{ color: '#6b7f76', fontSize: '0.82rem' }}>No case data available.</div>}
                </div>
                <div className="glass-panel">
                    <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Cases per MP</h3>
                    {data.mp_cases?.length > 0 ? (
                        <div>
                            {data.mp_cases.slice(0, 10).map(m => (
                                <div key={m.name} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                                    <div style={{ width: 120, fontSize: '0.82rem', fontWeight: 500, color: '#4a635a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.name}</div>
                                    <div style={{ flex: 1, background: '#e8efe9', borderRadius: 4, height: 22, overflow: 'hidden' }}>
                                        <div style={{
                                            width: `${Math.min(100, (m.cases / Math.max(...data.mp_cases.map(x => x.cases), 1)) * 100)}%`,
                                            height: '100%', background: 'linear-gradient(90deg, #0891b2, #06b6d4)', borderRadius: 4,
                                            display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: 6,
                                            fontSize: '0.7rem', color: 'white', fontWeight: 600,
                                        }}>{m.cases}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : <div style={{ color: '#6b7f76', fontSize: '0.82rem' }}>No MP data.</div>}
                </div>
            </div>

            {/* MP Activity */}
            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>MP Activity</h3>
                {data.activity?.length > 0 ? (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>MP</th>
                                <th>Constituency</th>
                                <th>Cases</th>
                                <th>Last Login</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.activity.map((a, i) => (
                                <tr key={i}>
                                    <td style={{ fontWeight: 500 }}>{a.mp}</td>
                                    <td>{a.constituency}</td>
                                    <td>{a.cases}</td>
                                    <td>{a.last_login}</td>
                                    <td>
                                        <span style={{ color: a.active ? '#059669' : '#9ca3af', fontSize: '0.8rem' }}>
                                            {a.active ? '🟢 Active' : '⚪ Never logged in'}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : <div style={{ color: '#6b7f76', fontSize: '0.82rem' }}>No MP activity data.</div>}
            </div>

            {/* Volume Chart */}
            <div className="glass-panel">
                <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Case Volume — Last 30 Days</h3>
                {data.volume_30d?.length > 0 ? (
                    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 120 }}>
                        {data.volume_30d.map((v, i) => {
                            const max = Math.max(...data.volume_30d.map(x => x.count), 1);
                            return (
                                <div key={i} title={`${v.day}: ${v.count} cases`} style={{
                                    flex: 1, background: 'linear-gradient(180deg, #006a4d, #059669)',
                                    borderRadius: '3px 3px 0 0', height: `${(v.count / max) * 100}%`,
                                    minHeight: 2, cursor: 'pointer', transition: 'opacity 0.2s',
                                }} />
                            );
                        })}
                    </div>
                ) : <div style={{ color: '#6b7f76', fontSize: '0.82rem' }}>No recent case data.</div>}
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

    const fetchCases = () => {
        const params = new URLSearchParams();
        if (filters.mp_id) params.set('mp_id', filters.mp_id);
        if (filters.period) params.set('period', filters.period);
        if (filters.category) params.set('category', filters.category);
        if (filters.status) params.set('status', filters.status);
        apiGet(`/api/admin/cases/explorer?${params.toString()}`).then(setData).catch(() => { });
    };

    useEffect(() => { fetchCases(); }, [filters]);

    const loadDetail = () => {
        if (!caseId) return;
        apiGet(`/api/admin/cases/${caseId}`).then(setDetail).catch(() => setDetail(null));
    };

    return (
        <>
            <div className="section-title">Case Explorer</div>

            {/* Filters */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: '1rem' }}>
                <div>
                    <label className="form-label">MP</label>
                    <select className="form-input" value={filters.mp_id} onChange={e => setFilters({ ...filters, mp_id: e.target.value })}>
                        <option value="">All MPs</option>
                        {data?.filter_options?.mps?.map(m => <option key={m.id} value={m.id}>{m.name} ({m.constituency})</option>)}
                    </select>
                </div>
                <div>
                    <label className="form-label">Period</label>
                    <select className="form-input" value={filters.period} onChange={e => setFilters({ ...filters, period: e.target.value })}>
                        <option value="">All Time</option>
                        <option value="7days">Last 7 Days</option>
                        <option value="30days">Last 30 Days</option>
                        <option value="90days">Last 90 Days</option>
                    </select>
                </div>
                <div>
                    <label className="form-label">Category</label>
                    <select className="form-input" value={filters.category} onChange={e => setFilters({ ...filters, category: e.target.value })}>
                        <option value="">All Categories</option>
                        {data?.filter_options?.categories?.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                </div>
                <div>
                    <label className="form-label">Status</label>
                    <select className="form-input" value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}>
                        <option value="">All Statuses</option>
                        {data?.filter_options?.statuses?.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                </div>
            </div>

            {data && <div style={{ color: '#6b7f76', fontSize: '0.78rem', marginBottom: 12 }}>Showing {Math.min(data.total, 200)} of {data.total?.toLocaleString()} cases</div>}

            {/* Cases Table */}
            {data?.cases?.length > 0 ? (
                <div className="glass-panel" style={{ overflow: 'auto', marginBottom: '1.5rem' }}>
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
                                    <td>{c.id}</td>
                                    <td style={{ fontWeight: 500 }}>{c.mp}</td>
                                    <td>{c.phone}</td>
                                    <td>{c.category}</td>
                                    <td>{c.status}</td>
                                    <td>{c.location}</td>
                                    <td>{c.assembly}</td>
                                    <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.message}</td>
                                    <td>{c.created}</td>
                                    <td>{c.critical ? '🔴' : ''}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            ) : (
                <div className="glass-panel" style={{ textAlign: 'center', color: '#6b7f76', padding: '2rem', marginBottom: '1.5rem' }}>
                    No cases match the selected filters.
                </div>
            )}

            {/* Case Detail */}
            <div className="glass-panel">
                <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Case Detail Lookup</h3>
                <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                    <input className="form-input" type="number" min={1} placeholder="Enter Case ID" value={caseId} onChange={e => setCaseId(e.target.value)} style={{ flex: 1 }} />
                    <button className="btn-primary" onClick={loadDetail}>Lookup</button>
                </div>
                {detail && (
                    <div style={{ border: '1px solid #e2ebe5', borderRadius: 12, padding: '1.2rem' }}>
                        <h4 style={{ marginBottom: 12, color: '#1a2e28' }}>Case #{detail.id}</h4>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 16 }}>
                            <div><div className="form-label">MP</div><div>{detail.mp_name}</div></div>
                            <div><div className="form-label">Constituency</div><div>{detail.mp_constituency}</div></div>
                            <div><div className="form-label">Phone</div><div>{detail.phone}</div></div>
                            <div><div className="form-label">Category</div><div>{detail.category}</div></div>
                            <div><div className="form-label">Status</div><div>{detail.status}</div></div>
                            <div><div className="form-label">Critical</div><div>{detail.critical ? 'Yes 🔴' : 'No'}</div></div>
                            <div><div className="form-label">Location</div><div>{detail.location}</div></div>
                            <div><div className="form-label">Assembly</div><div>{detail.assembly}</div></div>
                            <div><div className="form-label">Confidence</div><div>{detail.confidence}</div></div>
                        </div>
                        <hr style={{ border: 'none', borderTop: '1px solid #e2ebe5', margin: '12px 0' }} />
                        <div className="form-label">Full Message</div>
                        <pre style={{ background: '#f8faf9', padding: 12, borderRadius: 8, fontSize: '0.82rem', whiteSpace: 'pre-wrap', marginBottom: 12 }}>{detail.raw_message}</pre>
                        {detail.response_to_citizen && (
                            <><div className="form-label">AI Response to Citizen</div>
                                <pre style={{ background: '#f0fdf4', padding: 12, borderRadius: 8, fontSize: '0.82rem', whiteSpace: 'pre-wrap', marginBottom: 12 }}>{detail.response_to_citizen}</pre></>
                        )}
                        {detail.notes_for_staff && (
                            <><div className="form-label">Staff Notes</div>
                                <pre style={{ background: '#fffbeb', padding: 12, borderRadius: 8, fontSize: '0.82rem', whiteSpace: 'pre-wrap', marginBottom: 12 }}>{detail.notes_for_staff}</pre></>
                        )}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, color: '#6b7f76', fontSize: '0.75rem' }}>
                            <div>Created: {detail.created_at}</div>
                            <div>Updated: {detail.updated_at}</div>
                            <div>Resolved: {detail.resolved_at}</div>
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
    if (!data) return <div style={{ color: '#6b7f76', padding: '2rem', textAlign: 'center' }}>Loading...</div>;

    return (
        <>
            <div className="section-title">Grievance Analytics</div>

            {/* Category Breakdown */}
            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Most Common Grievance Categories</h3>
                {data.category_breakdown?.length > 0 ? (
                    <div>
                        {data.category_breakdown.slice(0, 12).map((c, i) => (
                            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                                <div style={{ width: 140, fontSize: '0.82rem', fontWeight: 500, color: '#4a635a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.category}</div>
                                <div style={{ width: 100, fontSize: '0.72rem', color: '#6b7f76' }}>{c.constituency}</div>
                                <div style={{ flex: 1, background: '#e8efe9', borderRadius: 4, height: 18, overflow: 'hidden' }}>
                                    <div style={{
                                        width: `${Math.min(100, (c.count / Math.max(...data.category_breakdown.map(x => x.count), 1)) * 100)}%`,
                                        height: '100%', background: 'linear-gradient(90deg, #d97706, #f59e0b)', borderRadius: 4,
                                        display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: 6,
                                        fontSize: '0.65rem', color: 'white', fontWeight: 600,
                                    }}>{c.count}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : <div style={{ color: '#6b7f76', fontSize: '0.82rem' }}>No category data.</div>}
            </div>

            {/* Category Volume + Status Distribution */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: '1.5rem' }}>
                <div className="glass-panel">
                    <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Category Volume (All MPs)</h3>
                    {data.category_volume?.length > 0 ? (
                        <table className="data-table">
                            <thead><tr><th>Category</th><th>Count</th></tr></thead>
                            <tbody>{data.category_volume.map(c => <tr key={c.category}><td>{c.category}</td><td>{c.count}</td></tr>)}</tbody>
                        </table>
                    ) : <div style={{ color: '#6b7f76', fontSize: '0.82rem' }}>No data.</div>}
                </div>
                <div className="glass-panel">
                    <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Status Distribution</h3>
                    {data.status_distribution?.length > 0 ? (
                        <table className="data-table">
                            <thead><tr><th>Status</th><th>Count</th></tr></thead>
                            <tbody>{data.status_distribution.map(s => <tr key={s.status}><td>{s.status}</td><td>{s.count}</td></tr>)}</tbody>
                        </table>
                    ) : <div style={{ color: '#6b7f76', fontSize: '0.82rem' }}>No data.</div>}
                </div>
            </div>

            {/* Resolution Times */}
            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Average Resolution Time</h3>
                {data.resolution_times?.length > 0 ? (
                    <table className="data-table">
                        <thead><tr><th>MP</th><th>Constituency</th><th>Resolved Cases</th><th>Avg Resolution Time</th></tr></thead>
                        <tbody>{data.resolution_times.map((r, i) => <tr key={i}><td>{r.mp}</td><td>{r.constituency}</td><td>{r.resolved_cases}</td><td>{r.avg_resolution_time}</td></tr>)}</tbody>
                    </table>
                ) : <div style={{ color: '#6b7f76', fontSize: '0.82rem' }}>No resolution data available yet.</div>}
            </div>

            {/* Assembly Distribution */}
            <div className="glass-panel">
                <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Cases by Assembly Constituency</h3>
                {data.assembly_distribution?.length > 0 ? (
                    <div>
                        {data.assembly_distribution.slice(0, 15).map((a, i) => (
                            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                                <div style={{ width: 160, fontSize: '0.82rem', fontWeight: 500, color: '#4a635a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.assembly}</div>
                                <div style={{ flex: 1, background: '#e8efe9', borderRadius: 4, height: 18, overflow: 'hidden' }}>
                                    <div style={{
                                        width: `${Math.min(100, (a.cases / Math.max(...data.assembly_distribution.map(x => x.cases), 1)) * 100)}%`,
                                        height: '100%', background: 'linear-gradient(90deg, #8d153a, #b91c50)', borderRadius: 4,
                                        display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: 6,
                                        fontSize: '0.65rem', color: 'white', fontWeight: 600,
                                    }}>{a.cases}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : <div style={{ color: '#6b7f76', fontSize: '0.82rem' }}>No assembly-level data.</div>}
            </div>
        </>
    );
}

/* ═══ Metric Card ═══ */
function MetricCard({ icon, value, label }) {
    return (
        <div style={{
            background: 'linear-gradient(135deg, #f8f9fa, #e9ecef)',
            borderRadius: 12, padding: 20, textAlign: 'center',
            border: '1px solid #dee2e6',
        }}>
            <div style={{ fontSize: 28, marginBottom: 4 }}>{icon}</div>
            <div style={{ fontSize: 28, fontWeight: 800, color: '#1a1a2e' }}>{value}</div>
            <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>{label}</div>
        </div>
    );
}
