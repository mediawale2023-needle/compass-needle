'use client';
import { useState, useEffect } from 'react';
import { apiGet } from '@/lib/api';

function formatDate(isoStr) {
    if (!isoStr) return '—';
    try {
        return new Date(isoStr).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return isoStr; }
}

const actionColors = {
    created: { bg: '#f0fdf4', color: '#065f46' },
    updated: { bg: '#eff6ff', color: '#1e40af' },
    deleted: { bg: '#fff1f2', color: '#be123c' },
    suspended: { bg: '#fffbeb', color: '#92400e' },
};

function parseSummary(summary) {
    if (!summary) return null;
    if (typeof summary === 'object') return summary;
    try {
        return JSON.parse(summary);
    } catch {
        return null;
    }
}

function summarizeDetails(entry) {
    const parsed = parseSummary(entry.change_summary);
    if (!parsed) return { summary: entry.change_summary || '—', parsed: null };

    const parts = [];
    if (parsed.alias) parts.push(`alias: ${parsed.alias}`);
    if (parsed.assembly) parts.push(`assembly: ${parsed.assembly}`);
    if (parsed.before_assembly || parsed.after_assembly) {
        parts.push(`assembly: ${parsed.before_assembly || '—'} -> ${parsed.after_assembly || '—'}`);
    }
    if (parsed.before?.stations !== undefined || parsed.after?.stations !== undefined) {
        parts.push(`stations: ${parsed.before?.stations ?? '—'} -> ${parsed.after?.stations ?? '—'}`);
    }
    if (parsed.seat_key) parts.push(`seat: ${parsed.seat_key}`);
    if (parsed.tenant_id) parts.push(`tenant: ${parsed.tenant_id}`);
    if (parsed.added_locality) parts.push(`added: ${parsed.added_locality}`);
    if (parsed.mode) parts.push(`mode: ${parsed.mode}`);

    return {
        summary: parts.join(' • ') || 'View details',
        parsed,
    };
}

export default function AuditLogPage() {
    const [entries, setEntries] = useState([]);
    const [filterOptions, setFilterOptions] = useState({ actors: [], actions: [], target_types: [] });
    const [actor, setActor] = useState('');
    const [action, setAction] = useState('');
    const [targetType, setTargetType] = useState('');
    const [days, setDays] = useState(30);
    const [loading, setLoading] = useState(true);

    const fetchLogs = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (actor) params.set('actor', actor);
            if (action) params.set('action', action);
            if (targetType) params.set('target_type', targetType);
            params.set('days', String(days));
            const data = await apiGet(`/api/admin/audit?${params.toString()}`);
            setEntries(data.entries || []);
            setFilterOptions(data.filter_options || { actors: [], actions: [], target_types: [] });
        } catch (e) {
            console.error('Failed to fetch audit log:', e);
        }
        setLoading(false);
    };

    useEffect(() => { fetchLogs(); }, [actor, action, targetType, days]);

    return (
        <>
            <h1 className="page-title">Audit Log</h1>
            <p className="page-desc">Track all administrative actions across the platform.</p>

            {/* Filters */}
            <div className="glass-panel" style={{ marginBottom: 16, padding: '0.875rem 1.25rem' }}>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                    <select className="form-input" value={actor} onChange={e => setActor(e.target.value)}
                        style={{ width: 160, fontSize: '0.78rem' }}>
                        <option value="">All actors</option>
                        {filterOptions.actors.map(a => <option key={a} value={a}>{a}</option>)}
                    </select>
                    <select className="form-input" value={action} onChange={e => setAction(e.target.value)}
                        style={{ width: 140, fontSize: '0.78rem' }}>
                        <option value="">All actions</option>
                        {filterOptions.actions.map(a => <option key={a} value={a}>{a}</option>)}
                    </select>
                    <select className="form-input" value={targetType} onChange={e => setTargetType(e.target.value)}
                        style={{ width: 160, fontSize: '0.78rem' }}>
                        <option value="">All targets</option>
                        {filterOptions.target_types.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                    <select className="form-input" value={days} onChange={e => setDays(Number(e.target.value))}
                        style={{ width: 130, fontSize: '0.78rem' }}>
                        <option value={7}>Last 7 days</option>
                        <option value={30}>Last 30 days</option>
                        <option value={90}>Last 90 days</option>
                        <option value={365}>Last year</option>
                    </select>
                    {(actor || action || targetType) && (
                        <button className="btn-ghost" onClick={() => { setActor(''); setAction(''); setTargetType(''); }}>
                            Clear filters
                        </button>
                    )}
                </div>
            </div>

            {/* Log Entries */}
            <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                {loading ? (
                    <div style={{ padding: '2rem', textAlign: 'center' }}>
                        <div className="skeleton" style={{ width: 200, height: 20, margin: '0 auto 10px' }} />
                        <div className="skeleton" style={{ width: 300, height: 16, margin: '0 auto' }} />
                    </div>
                ) : entries.length === 0 ? (
                    <div className="empty-state">
                        <div className="empty-state-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
                            </svg>
                        </div>
                        <div className="empty-state-title">No audit entries</div>
                        <div className="empty-state-desc">Actions will appear here as they happen.</div>
                    </div>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Admin</th>
                                <th>Action</th>
                                <th>Target</th>
                                <th>Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            {entries.map((e, i) => {
                                const ac = actionColors[e.action] || { bg: '#f8fafc', color: '#64748b' };
                                const detail = summarizeDetails(e);
                                return (
                                    <tr key={e.id || i}>
                                        <td style={{ fontSize: '0.72rem', color: '#6b7f76', whiteSpace: 'nowrap' }}>
                                            {formatDate(e.created_at)}
                                        </td>
                                        <td>
                                            <span style={{ fontWeight: 500, fontSize: '0.8rem' }}>{e.admin_username}</span>
                                        </td>
                                        <td>
                                            <span className="badge" style={{ background: ac.bg, color: ac.color }}>
                                                {e.action}
                                            </span>
                                        </td>
                                        <td>
                                            <span className="badge badge-slate">{e.target_type}</span>
                                            {e.target_name && (
                                                <span style={{ marginLeft: 6, fontSize: '0.76rem', color: '#1a2e28', fontWeight: 500 }}>
                                                    {e.target_name}
                                                </span>
                                            )}
                                        </td>
                                        <td style={{ fontSize: '0.72rem', color: '#6b7f76', maxWidth: 340 }}>
                                            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                {detail.summary}
                                            </div>
                                            {detail.parsed && (
                                                <details style={{ marginTop: 6 }}>
                                                    <summary style={{ cursor: 'pointer', color: '#456357' }}>View payload</summary>
                                                    <pre style={{
                                                        marginTop: 8,
                                                        padding: '0.75rem',
                                                        background: '#f6f8f7',
                                                        border: '1px solid #e2ebe5',
                                                        borderRadius: 8,
                                                        whiteSpace: 'pre-wrap',
                                                        wordBreak: 'break-word',
                                                        color: '#456357',
                                                        fontSize: '0.68rem',
                                                    }}>
                                                        {JSON.stringify(detail.parsed, null, 2)}
                                                    </pre>
                                                </details>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>

            <div style={{ marginTop: 10, fontSize: '0.68rem', color: '#94a3a0', textAlign: 'right' }}>
                Showing {entries.length} entries
            </div>
        </>
    );
}
