'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { apiGet } from '@/lib/api';
import { AdminDataState, AdminMetricStrip, AdminPageHeader, AdminPanel, AdminTableWrap } from '@/components/admin-ui/AdminPrimitives';

function timeAgo(value) {
    if (!value) return 'No observation';
    const seconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000);
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr ago`;
    return `${Math.floor(seconds / 86400)} d ago`;
}

function alertDestination(alert) {
    const query = alert.tenant_id ? `?tenant_id=${encodeURIComponent(alert.tenant_id)}` : '';
    if (alert.type === 'setup_incomplete') return `/dashboard/mps/${alert.tenant_id}/setup`;
    if (alert.type === 'low_completeness') return `/dashboard/accounts${query}`;
    if (alert.type === 'tenant_inactive') return `/dashboard/system/health${query}`;
    if (alert.type?.startsWith('whatsapp_inbound')) return '/dashboard/system/whatsapp-inbound';
    if (alert.type === 'whatsapp_health') return '/dashboard/system/whatsapp';
    if (alert.type?.startsWith('job_')) return '/dashboard/system/jobs';
    if (alert.type === 'expiring_announcement') return '/dashboard/system/announcements';
    return alert.tenant_id ? `/dashboard/mps/${alert.tenant_id}` : '/dashboard/system/health';
}

function severityLabel(severity) {
    if (severity === 'critical' || severity === 'error') return 'Critical';
    if (severity === 'warning') return 'Warning';
    return 'Review';
}

function ActionQueue({ alerts, loading, error, onRetry }) {
    const sorted = useMemo(() => [...alerts].sort((a, b) => {
        const rank = { critical: 0, error: 0, warning: 1, info: 2 };
        return (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3);
    }), [alerts]);
    return (
        <AdminPanel title="Needs attention now" description="Live operational alerts ordered by severity. Open an item to continue with its account or system context." actions={<Link className="btn-secondary" href="/dashboard/staff-access/audit">Audit log</Link>}>
            <AdminDataState loading={loading} error={error} empty={!loading && !error && sorted.length === 0} emptyTitle="No active operational alerts" emptyDescription="All alert checks completed and returned no current issues." onRetry={onRetry}>
                <div className="admin-action-queue">
                    {sorted.slice(0, 8).map((alert, index) => (
                        <Link key={`${alert.type}-${alert.tenant_id || 'global'}-${index}`} href={alertDestination(alert)} className="admin-action-row" data-severity={alert.severity || 'info'}>
                            <span className="admin-action-severity">{severityLabel(alert.severity)}</span>
                            <span className="admin-action-copy"><strong>{alert.title}</strong><small>{alert.description}</small></span>
                            <span className="admin-action-scope">{alert.tenant_id ? `Account #${alert.tenant_id}` : 'Platform'}</span>
                            <span aria-hidden="true" className="admin-action-arrow">→</span>
                        </Link>
                    ))}
                </div>
            </AdminDataState>
        </AdminPanel>
    );
}

function ReadinessSummary({ stats, accounts, alerts, unavailable }) {
    const items = useMemo(() => {
        const blocked = alerts.filter((item) => item.type === 'setup_incomplete').length;
        const stale = alerts.filter((item) => item.type === 'tenant_inactive').length;
        const lowProfiles = alerts.filter((item) => item.type === 'low_completeness').length;
        const missingWhatsApp = accounts.filter((item) => !item.whatsapp_number || String(item.whatsapp_number).startsWith('temp_')).length;
        return [
            { label: 'Open alerts', value: alerts.length, tone: alerts.length ? 'danger' : 'success' },
            { label: 'Blocked launches', value: blocked, tone: blocked ? 'warning' : 'success' },
            { label: 'Stale accounts', value: stale, tone: stale ? 'warning' : 'neutral' },
            { label: 'Low profiles', value: lowProfiles, tone: lowProfiles ? 'warning' : 'neutral' },
            { label: 'Missing WhatsApp', value: missingWhatsApp, tone: missingWhatsApp ? 'danger' : 'success' },
            { label: 'Total cases', value: stats?.total_cases ?? '—' },
        ];
    }, [accounts, alerts, stats]);
    return <AdminMetricStrip items={items} unavailable={unavailable} />;
}

function SystemHealth({ health, loading, error, onRetry }) {
    const services = health ? [
        { label: 'WhatsApp', status: health.whatsapp?.status || 'red', detail: health.whatsapp?.reason || (health.whatsapp?.last_webhook ? `Last webhook ${timeAgo(health.whatsapp.last_webhook)}` : 'No webhook observation'), href: '/dashboard/system/whatsapp' },
        { label: 'OpenAI', status: health.openai?.status || 'red', detail: health.openai?.configured ? 'Configured' : 'Not configured', href: '/dashboard/cases-intelligence/engine' },
        { label: 'Gemini', status: health.gemini?.status || 'red', detail: health.gemini?.configured ? 'Configured' : 'Not configured', href: '/dashboard/cases-intelligence/engine' },
    ] : [];
    return (
        <AdminPanel title="Platform readiness" description={health?.last_checked ? `Last checked ${timeAgo(health.last_checked)}` : 'Live service configuration and messaging health.'} actions={<Link href="/dashboard/system/health" className="btn-secondary">Open system health</Link>}>
            <AdminDataState loading={loading} error={error} onRetry={onRetry}>
                <div className="admin-health-grid">
                    {services.map((service) => (
                        <Link key={service.label} href={service.href} className="admin-health-service">
                            <span className="admin-health-dot" data-status={service.status} />
                            <span><strong>{service.label}</strong><small>{service.detail}</small></span>
                            <span aria-hidden="true">→</span>
                        </Link>
                    ))}
                </div>
            </AdminDataState>
        </AdminPanel>
    );
}

function AccountActivity({ accounts, loading, error, onRetry }) {
    const [query, setQuery] = useState('');
    const [filter, setFilter] = useState('all');
    const visible = useMemo(() => accounts.filter((account) => {
        if (filter === 'setup' && (account.completeness || 0) >= 70) return false;
        if (filter === 'whatsapp' && account.whatsapp_number && !String(account.whatsapp_number).startsWith('temp_')) return false;
        const haystack = `${account.display_name || ''} ${account.username || ''} ${account.parliamentary_constituency || ''}`.toLowerCase();
        return !query || haystack.includes(query.toLowerCase());
    }), [accounts, filter, query]);
    return (
        <AdminPanel title="Account readiness" description="Search customer accounts and continue with the next setup or support action." actions={<Link href="/dashboard/accounts/new" className="btn-primary">Create account</Link>}>
            <div className="admin-filter-bar">
                <label className="admin-search-field"><span className="sr-only">Search accounts</span><input className="form-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, seat, or username" /></label>
                <div className="admin-filter-pills" aria-label="Account filters">
                    {[['all', 'All'], ['setup', 'Needs setup'], ['whatsapp', 'Missing WhatsApp']].map(([value, label]) => <button type="button" key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}
                </div>
            </div>
            <AdminDataState loading={loading} error={error} empty={!loading && !error && visible.length === 0} emptyTitle="No accounts match this view" emptyDescription="Change the search or readiness filter to see other accounts." onRetry={onRetry}>
                <AdminTableWrap label="Account readiness registry">
                    <table className="data-table admin-command-table">
                        <thead><tr><th>Account</th><th>Seat</th><th>Stage</th><th>Profile</th><th>WhatsApp</th><th>Next action</th></tr></thead>
                        <tbody>{visible.slice(0, 12).map((account) => {
                            const incomplete = (account.completeness || 0) < 70;
                            const missingWhatsApp = !account.whatsapp_number || String(account.whatsapp_number).startsWith('temp_');
                            return <tr key={account.tenant_id}>
                                <td><strong>{account.display_name}</strong><small>@{account.username} · Account #{account.tenant_id}</small></td>
                                <td>{account.parliamentary_constituency || 'Not assigned'}<small>{account.seat_type?.toUpperCase() || account.house || '—'}</small></td>
                                <td><span className={`badge ${account.account_stage === 'aspirant' ? 'badge-amber' : 'badge-green'}`}>{account.account_stage || 'elected'}</span></td>
                                <td><span className="cn-data">{account.completeness || 0}%</span></td>
                                <td>{missingWhatsApp ? <span className="badge badge-red">Missing</span> : <span className="badge badge-green">Configured</span>}</td>
                                <td><Link href={incomplete ? `/dashboard/mps/${account.tenant_id}/setup` : `/dashboard/mps/${account.tenant_id}`}>{incomplete ? 'Continue setup' : 'Open account'} →</Link></td>
                            </tr>;
                        })}</tbody>
                    </table>
                </AdminTableWrap>
            </AdminDataState>
        </AdminPanel>
    );
}

export default function DashboardOverview() {
    const [stats, setStats] = useState(null);
    const [accounts, setAccounts] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [health, setHealth] = useState(null);
    const [state, setState] = useState({ stats: 'loading', accounts: 'loading', alerts: 'loading', health: 'loading' });
    const [errors, setErrors] = useState({});
    const loadResource = useCallback(async (key, path, apply) => {
        setState((current) => ({ ...current, [key]: 'loading' }));
        setErrors((current) => ({ ...current, [key]: '' }));
        try {
            const result = await apiGet(path); apply(result); setState((current) => ({ ...current, [key]: 'ready' }));
        } catch (error) {
            setErrors((current) => ({ ...current, [key]: error.message || `Failed to load ${key}` }));
            setState((current) => ({ ...current, [key]: 'error' }));
        }
    }, []);
    const loaders = useMemo(() => ({
        stats: () => loadResource('stats', '/api/admin/stats', setStats),
        accounts: () => loadResource('accounts', '/api/admin/mps', (result) => setAccounts(result.mps || [])),
        alerts: () => loadResource('alerts', '/api/admin/alerts', (result) => setAlerts(result.alerts || [])),
        health: () => loadResource('health', '/api/admin/system-health', setHealth),
    }), [loadResource]);
    useEffect(() => { Object.values(loaders).forEach((load) => load()); }, [loaders]);
    const summaryUnavailable = state.stats === 'error' || state.accounts === 'error' || state.alerts === 'error';
    return <div className="space-y-5">
        <AdminPageHeader title="Command Centre" description="Prioritise failures and launch blockers, then move directly into the affected account or operating system." actions={<button className="btn-secondary" type="button" onClick={() => Object.values(loaders).forEach((load) => load())}>Refresh all</button>} />
        <ActionQueue alerts={alerts} loading={state.alerts === 'loading'} error={errors.alerts} onRetry={loaders.alerts} />
        <ReadinessSummary stats={stats} accounts={accounts} alerts={alerts} unavailable={summaryUnavailable} />
        <div className="admin-command-grid">
            <SystemHealth health={health} loading={state.health === 'loading'} error={errors.health} onRetry={loaders.health} />
            <AdminPanel title="Operational activity" description="Current platform totals from the Admin reporting API.">
                <AdminDataState loading={state.stats === 'loading'} error={errors.stats} onRetry={loaders.stats}>
                    <dl className="admin-activity-list">
                        <div><dt>Customer accounts</dt><dd>{stats?.total_accounts ?? stats?.total_mps ?? '—'}</dd></div>
                        <div><dt>MP seats</dt><dd>{stats?.mp_seats ?? stats?.lok_sabha ?? '—'}</dd></div>
                        <div><dt>MLA seats</dt><dd>{stats?.mla_seats ?? '—'}</dd></div>
                        <div><dt>Aspirants</dt><dd>{stats?.aspirants ?? '—'}</dd></div>
                        <div><dt>Profiles</dt><dd>{stats?.total_profiles ?? '—'}</dd></div>
                    </dl>
                </AdminDataState>
            </AdminPanel>
        </div>
        <AccountActivity accounts={accounts} loading={state.accounts === 'loading'} error={errors.accounts} onRetry={loaders.accounts} />
    </div>;
}
