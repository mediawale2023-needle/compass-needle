'use client';

import { useEffect, useMemo, useState } from 'react';
import { apiGet } from '@/lib/api';
import { AdminDataState, AdminMetricStrip, AdminPageHeader, AdminPanel, AdminTableWrap } from '@/components/admin-ui/AdminPrimitives';

function timeAgo(value) {
    if (!value) return '—';
    const diff = (Date.now() - new Date(value).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hr ago`;
    return `${Math.floor(diff / 86400)} d ago`;
}

function statusBadgeClass(status) {
    return status === 'success' ? 'badge badge-green' : status === 'failed' ? 'badge badge-red' : status === 'running' ? 'badge badge-amber' : 'badge badge-slate';
}

function safeSummary(value) {
    if (!value) return '—';
    if (typeof value === 'string') return value;
    return Object.entries(value).map(([key, item]) => `${key}: ${String(item)}`).join(' · ');
}

export default function JobRunsPage() {
    const [data, setData] = useState(null);
    const [status, setStatus] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const load = async (nextStatus = status) => {
        setLoading(true); setError('');
        try {
            const suffix = nextStatus ? `?status=${encodeURIComponent(nextStatus)}` : '';
            setData(await apiGet(`/api/admin/jobs${suffix}`));
        } catch (err) { setError(err.message || 'Job history could not be loaded.'); }
        finally { setLoading(false); }
    };

    useEffect(() => { load(''); }, []);
    const items = data?.items || [];
    const summary = data?.summary || {};
    const metrics = useMemo(() => ([
        { label: 'Running', value: summary.running || 0, tone: 'warning' }, { label: 'Failed', value: summary.failed || 0, tone: 'danger' },
        { label: 'Queued', value: summary.queued || 0 }, { label: 'Succeeded', value: summary.success || 0, tone: 'success' },
    ]), [summary]);

    return <div className="space-y-6">
        <AdminPageHeader context="Platform Operations / Jobs" title="Job runs" description="Trace background and administrator-triggered operations without exposing credentials or raw payloads." actions={<button type="button" className="btn-secondary" onClick={() => load()} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button>} />
        <AdminMetricStrip unavailable={Boolean(error)} items={metrics} />
        <AdminPanel title="Recent operations" description="Seat maps, boundary imports, Parliament resolution, and Parliament backfill share this history." actions={<label className="admin-inline-filter"><span>Status</span><select className="form-select" value={status} onChange={(event) => { setStatus(event.target.value); load(event.target.value); }}><option value="">All statuses</option><option value="running">Running</option><option value="failed">Failed</option><option value="queued">Queued</option><option value="success">Succeeded</option></select></label>}>
            <AdminDataState loading={loading} error={error} empty={!loading && !error && items.length === 0} emptyTitle="No job runs found" emptyDescription="Change the status filter or wait for an operation to run." onRetry={() => load()}>
                <AdminTableWrap label="Job run history"><table className="data-table"><thead><tr><th>Job</th><th>Scope</th><th>Status</th><th>Triggered by</th><th>Started</th><th>Finished</th><th>Summary</th><th>Error</th></tr></thead>
                    <tbody>{items.map((item) => <tr key={item.job_key}><td><strong>{item.job_type}</strong><small>{item.job_key}</small></td><td>{item.scope_type ? `${item.scope_type}:${item.scope_id || '—'}` : 'global'}</td><td><span className={statusBadgeClass(item.status)}>{item.status}</span></td><td>{item.triggered_by || 'system'}</td><td>{timeAgo(item.started_at || item.created_at)}</td><td>{timeAgo(item.finished_at)}</td><td className="admin-cell-wrap">{safeSummary(item.summary_json)}</td><td className="admin-cell-wrap">{item.error_text || '—'}</td></tr>)}</tbody>
                </table></AdminTableWrap>
            </AdminDataState>
        </AdminPanel>
    </div>;
}
