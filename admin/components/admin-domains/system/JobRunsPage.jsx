'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { apiGet } from '@/lib/api';

function timeAgo(isoStr) {
    if (!isoStr) return '—';
    const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hr ago`;
    return `${Math.floor(diff / 86400)} d ago`;
}

function statusBadgeClass(status) {
    if (status === 'success') return 'badge badge-green';
    if (status === 'failed') return 'badge badge-red';
    if (status === 'running') return 'badge badge-amber';
    if (status === 'queued') return 'badge badge-slate';
    return 'badge badge-slate';
}

export default function JobRunsPage() {
    const [data, setData] = useState(null);
    const [status, setStatus] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const load = async (nextStatus = status) => {
        setLoading(true);
        setError('');
        try {
            const suffix = nextStatus ? `?status=${encodeURIComponent(nextStatus)}` : '';
            const result = await apiGet(`/api/admin/jobs${suffix}`);
            setData(result);
        } catch (err) {
            setError(err.message || 'Failed to load jobs');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load('');
    }, []);

    const items = data?.items || [];
    const summary = data?.summary || {};
    const cards = useMemo(() => ([
        { label: 'Running', value: summary.running || 0, className: 'badge badge-amber' },
        { label: 'Failed', value: summary.failed || 0, className: 'badge badge-red' },
        { label: 'Queued', value: summary.queued || 0, className: 'badge badge-slate' },
        { label: 'Succeeded', value: summary.success || 0, className: 'badge badge-green' },
    ]), [summary]);

    return (
        <div className="space-y-6">
            <div className="admin-domain-hero">
                <div className="cn-eyebrow">Platform Control</div>
                <h2 className="cn-h1 mt-3">Job runs</h2>
                <p className="cn-body mt-3 max-w-3xl text-sm">
                    One shared history for background and admin-triggered operations. Use this to review failures, long-running work, and what changed.
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                    <Link href="/dashboard/system" className="btn-secondary" style={{ textDecoration: 'none' }}>
                        Back to system
                    </Link>
                    <button className="btn-primary" onClick={() => load()} disabled={loading}>
                        {loading ? 'Refreshing…' : 'Refresh'}
                    </button>
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
                {cards.map((card) => (
                    <div key={card.label} className="glass-panel">
                        <div className="cn-meta text-xs">{card.label}</div>
                        <div className="mt-3 flex items-center gap-3">
                            <span className={card.className}>{card.label}</span>
                            <div className="cn-h2">{card.value}</div>
                        </div>
                    </div>
                ))}
            </div>

            <div className="glass-panel">
                <div className="mb-4 flex items-center justify-between gap-4">
                    <div>
                        <h3 className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>Recent operations</h3>
                        <p className="cn-body mt-2 text-sm">
                            This first slice covers seat-map generation, boundary import, parliament resolution, and parliament backfill.
                        </p>
                    </div>
                    <select
                        className="form-select"
                        value={status}
                        onChange={(e) => {
                            setStatus(e.target.value);
                            load(e.target.value);
                        }}
                        style={{ minWidth: 170 }}
                    >
                        <option value="">All statuses</option>
                        <option value="running">Running</option>
                        <option value="failed">Failed</option>
                        <option value="queued">Queued</option>
                        <option value="success">Succeeded</option>
                    </select>
                </div>

                {error && <div className="toast toast-error" style={{ position: 'relative', marginBottom: 12 }}>{error}</div>}

                {items.length === 0 && !loading ? (
                    <p className="cn-body text-sm">No job runs found for the current filter.</p>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Job</th>
                                <th>Scope</th>
                                <th>Status</th>
                                <th>Triggered by</th>
                                <th>Started</th>
                                <th>Finished</th>
                                <th>Summary</th>
                                <th>Error</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items.map((item) => (
                                <tr key={item.job_key}>
                                    <td>
                                        <div>{item.job_type}</div>
                                        <div className="cn-meta text-xs">{item.job_key}</div>
                                    </td>
                                    <td>{item.scope_type ? `${item.scope_type}:${item.scope_id || '—'}` : 'global'}</td>
                                    <td><span className={statusBadgeClass(item.status)}>{item.status}</span></td>
                                    <td>{item.triggered_by || 'system'}</td>
                                    <td>{timeAgo(item.started_at || item.created_at)}</td>
                                    <td>{item.finished_at ? timeAgo(item.finished_at) : '—'}</td>
                                    <td style={{ maxWidth: 260 }}>
                                        <div className="cn-body text-sm">{item.summary_json ? JSON.stringify(item.summary_json) : '—'}</div>
                                    </td>
                                    <td style={{ maxWidth: 320 }}>
                                        <div className="cn-body text-sm">{item.error_text || '—'}</div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}
