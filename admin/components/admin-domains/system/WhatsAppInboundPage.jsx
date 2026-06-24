'use client';

import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '@/lib/api';

const STATUS_BADGES = {
    received: 'badge badge-amber badge-dot',
    processing: 'badge badge-blue badge-dot',
    processed: 'badge badge-green badge-dot',
    failed: 'badge badge-red badge-dot',
};

function formatDateTime(value) {
    if (!value) return '—';
    try {
        return new Date(value).toLocaleString('en-IN', {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    } catch {
        return value;
    }
}

export default function WhatsAppInboundPage() {
    const [rows, setRows] = useState([]);
    const [summary, setSummary] = useState(null);
    const [status, setStatus] = useState('');
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [retryingId, setRetryingId] = useState(null);

    const load = async () => {
        setLoading(true);
        setError('');
        try {
            const params = new URLSearchParams();
            if (status) params.set('status', status);
            if (query.trim()) params.set('q', query.trim());
            params.set('limit', '50');
            const data = await apiGet(`/api/admin/whatsapp/inbound?${params.toString()}`);
            setRows(data.rows || []);
            setSummary(data.summary || null);
        } catch (err) {
            setError(err.message || 'Failed to load inbound WhatsApp operations');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
        const timer = setInterval(load, 15000);
        return () => clearInterval(timer);
    }, [status]);

    const handleRetry = async (inboundId) => {
        setRetryingId(inboundId);
        setError('');
        try {
            await apiPost(`/api/admin/whatsapp/inbound/${inboundId}/retry`, {});
            await load();
        } catch (err) {
            setError(err.message || 'Retry failed');
        } finally {
            setRetryingId(null);
        }
    };

    return (
        <div className="space-y-6">
            <div className="admin-domain-hero">
                <div className="cn-eyebrow">Platform Control</div>
                <h2 className="cn-h1 mt-3">WhatsApp inbound operations</h2>
                <p className="cn-body mt-3 max-w-3xl text-sm">
                    Every inbound WhatsApp message is persisted before business logic runs. Use this queue to inspect stuck intake, failed rows,
                    and delivery retry history without guessing from cases alone.
                </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                    ['Received', summary?.received_count ?? 0],
                    ['Processing', summary?.processing_count ?? 0],
                    ['Failed', summary?.failed_count ?? 0],
                    ['Stale', (summary?.stale_received_count ?? 0) + (summary?.stale_processing_count ?? 0)],
                ].map(([label, value]) => (
                    <div key={label} className="stat-card">
                        <div style={{ fontSize: '1.9rem', fontWeight: 800, color: '#1a2e28', lineHeight: 1 }}>{value}</div>
                        <div style={{ color: '#6b7f76', fontSize: '0.72rem', fontWeight: 500, marginTop: 5, textTransform: 'uppercase', letterSpacing: '0.7px' }}>
                            {label}
                        </div>
                    </div>
                ))}
            </div>

            <div className="glass-panel" style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap' }}>
                <label style={{ minWidth: 180 }}>
                    <div className="cn-eyebrow mb-2">Status</div>
                    <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
                        <option value="">All statuses</option>
                        <option value="received">Received</option>
                        <option value="processing">Processing</option>
                        <option value="failed">Failed</option>
                        <option value="processed">Processed</option>
                    </select>
                </label>
                <label style={{ minWidth: 260 }}>
                    <div className="cn-eyebrow mb-2">Phone or message ID</div>
                    <input
                        className="input"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Search sender or Meta message ID"
                    />
                </label>
                <button className="btn-secondary" type="button" onClick={load} disabled={loading}>
                    {loading ? 'Refreshing…' : 'Refresh'}
                </button>
            </div>

            {error && <div className="toast toast-error">{error}</div>}

            <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Received</th>
                            <th>Status</th>
                            <th>Sender</th>
                            <th>Tenant</th>
                            <th>Type</th>
                            <th>Case</th>
                            <th>Preview</th>
                            <th>Error</th>
                            <th style={{ textAlign: 'right' }}>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading ? (
                            [...Array(6)].map((_, idx) => (
                                <tr key={idx}>
                                    <td colSpan={9}>
                                        <div className="skeleton" style={{ height: 36, borderRadius: 8 }} />
                                    </td>
                                </tr>
                            ))
                        ) : rows.length === 0 ? (
                            <tr>
                                <td colSpan={9} style={{ textAlign: 'center', color: '#6b7f76', padding: '2rem' }}>
                                    No inbound rows matched this filter.
                                </td>
                            </tr>
                        ) : rows.map((row) => (
                            <tr key={row.id}>
                                <td style={{ fontSize: '0.8rem', color: '#6b7f76' }}>
                                    {formatDateTime(row.last_received_at || row.created_at)}
                                    <div style={{ marginTop: 2, fontSize: '0.68rem', color: '#94a3a0' }}>
                                        {row.delivery_attempts || 1} deliveries / {row.retry_count || 0} retries
                                    </div>
                                </td>
                                <td><span className={STATUS_BADGES[row.status] || 'badge badge-slate'}>{row.status}</span></td>
                                <td style={{ fontWeight: 600 }}>
                                    {row.sender_phone}
                                    <div style={{ marginTop: 2, fontSize: '0.68rem', color: '#94a3a0' }}>{row.meta_message_id}</div>
                                </td>
                                <td style={{ color: '#6b7f76' }}>{row.tenant_id ? `Tenant #${row.tenant_id}` : 'Unresolved'}</td>
                                <td style={{ textTransform: 'capitalize' }}>{row.message_type || 'unknown'}</td>
                                <td>{row.case_id ? `Case #${row.case_id}` : '—'}</td>
                                <td style={{ maxWidth: 260, color: '#6b7f76' }}>{row.text_preview || '—'}</td>
                                <td style={{ maxWidth: 260, color: row.last_error ? '#9f1239' : '#94a3a0' }}>
                                    {row.last_error ? String(row.last_error).slice(0, 140) : '—'}
                                </td>
                                <td style={{ textAlign: 'right' }}>
                                    {row.status === 'processed' ? (
                                        <span style={{ color: '#94a3a0', fontSize: '0.82rem' }}>Healthy</span>
                                    ) : (
                                        <button
                                            className="btn-secondary"
                                            type="button"
                                            onClick={() => handleRetry(row.id)}
                                            disabled={retryingId === row.id}
                                        >
                                            {retryingId === row.id ? 'Retrying…' : 'Retry'}
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
