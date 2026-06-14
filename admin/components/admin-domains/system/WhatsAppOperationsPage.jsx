'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { apiGet, apiPost } from '@/lib/api';

function timeAgo(isoStr) {
    if (!isoStr) return '—';
    const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hr ago`;
    return `${Math.floor(diff / 86400)} d ago`;
}

function statusBadgeClass(status) {
    if (status === 'sent' || status === 'ok') return 'badge badge-green';
    if (status === 'failed' || status === 'fail') return 'badge badge-red';
    if (status === 'retrying' || status === 'pending') return 'badge badge-amber';
    return 'badge badge-slate';
}

function HealthCard({ title, value, detail, tone }) {
    return (
        <div className="glass-panel">
            <div className="cn-meta text-xs">{title}</div>
            <div className="mt-2 flex items-center gap-2">
                <span className={`badge badge-dot ${tone === 'red' ? 'badge-red' : tone === 'amber' ? 'badge-amber' : 'badge-green'}`}>
                    {tone === 'red' ? 'Action needed' : tone === 'amber' ? 'Watch' : 'Healthy'}
                </span>
            </div>
            <div className="cn-h3 mt-3">{value}</div>
            <p className="cn-body mt-2 text-sm">{detail}</p>
        </div>
    );
}

export default function WhatsAppOperationsPage() {
    const [diagnostics, setDiagnostics] = useState(null);
    const [outbound, setOutbound] = useState([]);
    const [health, setHealth] = useState(null);
    const [loading, setLoading] = useState(true);
    const [retryingId, setRetryingId] = useState(null);
    const [toast, setToast] = useState(null);

    const load = async () => {
        setLoading(true);
        try {
            const [diag, queue, sysHealth] = await Promise.all([
                apiGet('/api/admin/debug/whatsapp'),
                apiGet('/api/admin/whatsapp/outbound?page=1&page_size=100'),
                apiGet('/api/admin/system-health'),
            ]);
            setDiagnostics(diag);
            setOutbound(queue.items || []);
            setHealth(sysHealth);
        } catch (err) {
            setToast({ type: 'error', text: err.message || 'Failed to load WhatsApp operations' });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, []);

    const queue = useMemo(
        () => outbound.filter((item) => item.status === 'failed' || item.status === 'retrying' || item.status === 'pending'),
        [outbound],
    );

    const retryMessage = async (messageId) => {
        setRetryingId(messageId);
        try {
            await apiPost(`/api/admin/whatsapp/outbound/${messageId}/retry`, {});
            setToast({ type: 'success', text: `Retry queued for outbound message #${messageId}` });
            await load();
        } catch (err) {
            setToast({ type: 'error', text: err.message || `Retry failed for #${messageId}` });
        } finally {
            setRetryingId(null);
        }
    };

    const summary = diagnostics?.summary || {};
    const checks = diagnostics?.checks || [];
    const failedChecks = checks.filter((check) => check.status === 'fail');
    const waHealth = health?.whatsapp || {};
    const tenantIssues = waHealth?.routing?.tenant_issues || [];

    return (
        <div className="space-y-6">
            {toast?.text && (
                <div className={`toast ${toast.type === 'error' ? 'toast-error' : 'toast-success'}`}>
                    {toast.text}
                </div>
            )}

            <div className="admin-domain-hero">
                <div className="cn-eyebrow">Platform Control</div>
                <h2 className="cn-h1 mt-3">WhatsApp operations</h2>
                <p className="cn-body mt-3 max-w-3xl text-sm">
                    This is the operational view for Meta health and outbound citizen replies. Failed or pending sends stay here until an operator reviews or retries them.
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                    <Link href="/dashboard/system" className="btn-secondary" style={{ textDecoration: 'none' }}>
                        Back to system
                    </Link>
                    <button className="btn-primary" onClick={load} disabled={loading}>
                        {loading ? 'Refreshing…' : 'Refresh'}
                    </button>
                </div>
            </div>

            <div className="glass-panel">
                <div className="mb-4 flex items-start justify-between gap-4">
                    <div>
                        <div className="cn-meta text-xs">Current status</div>
                        <h3 className="cn-h2 mt-2">{
                            waHealth?.status === 'red'
                                ? 'WhatsApp is broken'
                                : waHealth?.status === 'amber'
                                    ? 'WhatsApp needs attention'
                                    : 'WhatsApp is healthy'
                        }</h3>
                        <p className="cn-body mt-2 text-sm">{waHealth?.reason || 'Health details unavailable.'}</p>
                    </div>
                    <span className={statusBadgeClass(waHealth?.status)}>{waHealth?.status || 'unknown'}</span>
                </div>
                <div className="grid gap-3 md:grid-cols-4">
                    <div className="rounded-[10px] border border-[var(--line)] bg-[var(--surface-2)] p-4">
                        <div className="cn-meta text-xs">Meta token</div>
                        <div className="mt-2">
                            <span className={statusBadgeClass(waHealth?.meta_token?.status)}>{waHealth?.meta_token?.status || 'unknown'}</span>
                        </div>
                        <p className="cn-body mt-3 text-sm">{waHealth?.meta_token?.detail || 'No token detail available.'}</p>
                    </div>
                    <div className="rounded-[10px] border border-[var(--line)] bg-[var(--surface-2)] p-4">
                        <div className="cn-meta text-xs">Webhook heartbeat</div>
                        <div className="mt-2">
                            <span className={statusBadgeClass(waHealth?.webhook?.status)}>{waHealth?.webhook?.status || 'unknown'}</span>
                        </div>
                        <p className="cn-body mt-3 text-sm">{waHealth?.webhook?.detail || 'No webhook detail available.'}</p>
                    </div>
                    <div className="rounded-[10px] border border-[var(--line)] bg-[var(--surface-2)] p-4">
                        <div className="cn-meta text-xs">Routing coverage</div>
                        <div className="mt-2">
                            <span className={statusBadgeClass(waHealth?.routing?.status)}>{waHealth?.routing?.status || 'unknown'}</span>
                        </div>
                        <p className="cn-body mt-3 text-sm">{waHealth?.routing?.detail || 'No routing detail available.'}</p>
                    </div>
                    <div className="rounded-[10px] border border-[var(--line)] bg-[var(--surface-2)] p-4">
                        <div className="cn-meta text-xs">Outbound delivery</div>
                        <div className="mt-2">
                            <span className={statusBadgeClass(waHealth?.outbound?.status)}>{waHealth?.outbound?.status || 'unknown'}</span>
                        </div>
                        <p className="cn-body mt-3 text-sm">{waHealth?.outbound?.detail || 'No outbound detail available.'}</p>
                    </div>
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
                <HealthCard
                    title="Meta stack"
                    tone={waHealth?.meta_token?.status === 'red' ? 'red' : waHealth?.meta_token?.status === 'amber' ? 'amber' : 'green'}
                    value={waHealth?.meta_token?.status === 'green' ? 'Token validated live' : 'Token needs review'}
                    detail={waHealth?.meta_token?.detail || summary.first_failure || 'Token, webhook, and tenant routing checks are healthy right now.'}
                />
                <HealthCard
                    title="Outbound queue"
                    tone={waHealth?.outbound?.status === 'red' ? 'red' : waHealth?.outbound?.status === 'amber' ? 'amber' : 'green'}
                    value={`${queue.length} pending or failed`}
                    detail={
                        waHealth?.outbound?.last_outbound_attempt
                            ? `Last attempt ${timeAgo(waHealth.outbound.last_outbound_attempt)}`
                            : 'No outbound attempts logged yet.'
                    }
                />
                <HealthCard
                    title="Recent webhooks"
                    tone={waHealth?.webhook?.status === 'red' ? 'red' : waHealth?.webhook?.status === 'amber' ? 'amber' : 'green'}
                    value={waHealth?.webhook?.last_webhook ? timeAgo(waHealth.webhook.last_webhook) : 'No inbound activity'}
                    detail={waHealth?.webhook?.detail || 'Inbound heartbeat still uses the latest case created from the webhook path.'}
                />
            </div>

            <div className="glass-panel">
                <div className="mb-4 flex items-start justify-between gap-4">
                    <div>
                        <h3 className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>Tenant routing gaps</h3>
                        <p className="cn-body mt-2 text-sm">
                            Active tenants missing their WhatsApp number or Meta phone number ID show up here so operators can fix routing before sends fail.
                        </p>
                    </div>
                    <span className={`badge ${tenantIssues.length ? 'badge-amber' : 'badge-green'}`}>
                        {tenantIssues.length ? `${tenantIssues.length} issue${tenantIssues.length === 1 ? '' : 's'}` : 'All covered'}
                    </span>
                </div>
                {tenantIssues.length ? (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Tenant</th>
                                <th>Constituency</th>
                                <th>Issue</th>
                            </tr>
                        </thead>
                        <tbody>
                            {tenantIssues.map((item) => (
                                <tr key={item.tenant_id}>
                                    <td>{item.name}</td>
                                    <td>{item.constituency || '—'}</td>
                                    <td>{item.issue}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : (
                    <p className="cn-body text-sm">All active tenants currently have routing coverage.</p>
                )}
            </div>

            <div className="glass-panel">
                <div className="mb-4 flex items-start justify-between gap-4">
                    <div>
                        <h3 className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>Current failures</h3>
                        <p className="cn-body mt-2 text-sm">
                            These checks come from the live Meta/token/webhook diagnostics endpoint. Fix the first failing check before chasing downstream symptoms.
                        </p>
                    </div>
                    <span className={`badge ${failedChecks.length ? 'badge-red' : 'badge-green'}`}>
                        {failedChecks.length ? `${failedChecks.length} failing` : 'All passing'}
                    </span>
                </div>

                {failedChecks.length ? (
                    <div className="space-y-3">
                        {failedChecks.map((check) => (
                            <div key={check.name} className="rounded-[10px] border border-[var(--line)] bg-[var(--surface-2)] p-4">
                                <div className="flex items-center gap-2">
                                    <span className={statusBadgeClass(check.status)}>{check.status}</span>
                                    <div className="cn-h3">{check.name}</div>
                                </div>
                                <p className="cn-body mt-2 text-sm">{check.detail}</p>
                                {check.fix && <p className="cn-body mt-2 text-sm"><strong>Next step:</strong> {check.fix}</p>}
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="cn-body text-sm">No failing diagnostics right now.</p>
                )}
            </div>

            <div className="glass-panel">
                <div className="mb-4 flex items-start justify-between gap-4">
                    <div>
                        <h3 className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>Outbound reply queue</h3>
                        <p className="cn-body mt-2 text-sm">
                            Every attempted citizen reply is now persisted here with status, tenant context, Meta response, and retry count.
                        </p>
                    </div>
                    <span className="badge badge-slate">{queue.length} visible</span>
                </div>

                {queue.length === 0 ? (
                    <p className="cn-body text-sm">No pending or failed outbound replies right now.</p>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>When</th>
                                <th>Tenant</th>
                                <th>Recipient</th>
                                <th>Status</th>
                                <th>Attempts</th>
                                <th>Case</th>
                                <th>Error</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {queue.map((item) => (
                                <tr key={item.id}>
                                    <td>{item.last_attempt_at ? timeAgo(item.last_attempt_at) : timeAgo(item.created_at)}</td>
                                    <td>
                                        <div>{item.tenant_name || 'Unknown tenant'}</div>
                                        <div className="cn-meta text-xs">{item.tenant_constituency || 'No constituency'}</div>
                                    </td>
                                    <td style={{ fontFamily: 'IBM Plex Mono, monospace' }}>{item.to_number}</td>
                                    <td><span className={statusBadgeClass(item.status)}>{item.status}</span></td>
                                    <td>{item.attempt_count || 0}</td>
                                    <td>{item.case_id || '—'}</td>
                                    <td style={{ maxWidth: 320 }}>
                                        <div className="cn-body text-sm">{item.last_error || '—'}</div>
                                    </td>
                                    <td>
                                        <button
                                            className="btn-secondary"
                                            style={{ whiteSpace: 'nowrap' }}
                                            disabled={retryingId === item.id}
                                            onClick={() => retryMessage(item.id)}
                                        >
                                            {retryingId === item.id ? 'Retrying…' : 'Retry'}
                                        </button>
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
