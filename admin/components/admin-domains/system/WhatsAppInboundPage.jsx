'use client';

import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '@/lib/api';
import { AdminDataState, AdminMetricStrip, AdminNotice, AdminPageHeader, AdminPanel, AdminTableWrap } from '@/components/admin-ui/AdminPrimitives';

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
            <AdminPageHeader context="Messaging & Sync / Inbound" title="WhatsApp inbound" description="Inspect the persisted intake ledger, processing state, failed rows, and retry history without inferring state from cases." />

            <AdminMetricStrip unavailable={Boolean(error)} items={[
                { label: 'Received', value: summary?.received_count ?? 0 }, { label: 'Processing', value: summary?.processing_count ?? 0, tone: 'warning' },
                { label: 'Failed', value: summary?.failed_count ?? 0, tone: 'danger' }, { label: 'Throttled', value: summary?.throttled_count ?? 0, tone: 'warning' },
                { label: 'Stale', value: (summary?.stale_received_count ?? 0) + (summary?.stale_processing_count ?? 0), tone: 'danger' },
            ]} />

            <div className="glass-panel" style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap' }}>
                <label style={{ minWidth: 180 }}>
                    <div className="cn-eyebrow mb-2">Status</div>
                    <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
                        <option value="">All statuses</option>
                        <option value="received">Received</option>
                        <option value="processing">Processing</option>
                        <option value="failed">Failed</option>
                        <option value="throttled">Throttled</option>
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

            <AdminNotice tone="warning" title="Retry safety">
                Only failed ledger rows can be retried here. Received or processing rows may still be owned by a worker and require investigation before another attempt.
            </AdminNotice>

            <AdminPanel title="Inbound ledger" description="Rows refresh every 15 seconds. Search applies when Refresh is selected.">
              <AdminDataState loading={loading} error={error} empty={!loading && !error && rows.length === 0} emptyTitle="No inbound rows matched" emptyDescription="Change the filters or wait for new inbound activity." onRetry={load}>
               <AdminTableWrap label="WhatsApp inbound ledger">
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
                        {rows.map((row) => (
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
                                    {row.status === 'failed' ? (
                                        <button
                                            className="btn-secondary"
                                            type="button"
                                            onClick={() => handleRetry(row.id)}
                                            disabled={retryingId === row.id}
                                        >
                                            {retryingId === row.id ? 'Retrying…' : 'Retry'}
                                        </button>
                                    ) : (
                                        <span className="admin-muted-action">{row.status === 'processed' ? 'Complete' : 'Investigate'}</span>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
               </AdminTableWrap>
              </AdminDataState>
            </AdminPanel>
        </div>
    );
}
