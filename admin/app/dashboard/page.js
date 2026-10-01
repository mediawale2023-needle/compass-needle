'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { apiGet } from '@/lib/api';
import { AdminDataState, AdminMetricStrip, AdminPageHeader, AdminPanel, AdminTableWrap } from '@/components/admin-ui/AdminPrimitives';

// Compact relative age, matching the Briefcase convention (formatBriefcaseAge
// in frontend/components/briefcase/briefcase-shared.jsx): a single unit, never
// a date where an age will do. Duplicated rather than imported because
// frontend/ and admin/ are separate npm projects with no shared package.
function formatAge(value) {
    if (!value) return null;
    const ms = Date.now() - new Date(value).getTime();
    if (Number.isNaN(ms)) return null;
    const minutes = Math.max(1, Math.floor(ms / 60000));
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h`;
    return `${Math.floor(hours / 24)}d`;
}

// Preserved verbatim — these destinations are existing behaviour.
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

// ─── Attention strip ──────────────────────────────────────────────────────
// Every counter is a direct count of real records. A category whose source
// failed to load reports "Unavailable" rather than a misleading zero.
function AttentionStrip({ stats, alerts, alertsReady, statsReady }) {
    const items = useMemo(() => {
        const bySeverity = (match) => alerts.filter((a) => match.includes(a.severity)).length;
        const critical = bySeverity(['critical', 'error']);
        const warning = bySeverity(['warning']);
        const review = alerts.length - critical - warning;
        const seats = statsReady && (stats?.mp_seats != null || stats?.mla_seats != null)
            ? (stats?.mp_seats || 0) + (stats?.mla_seats || 0)
            : null;
        return [
            { label: 'Critical', value: critical, tone: critical ? 'danger' : 'success', unavailable: !alertsReady },
            { label: 'Warning', value: warning, tone: warning ? 'warning' : 'neutral', unavailable: !alertsReady },
            { label: 'Review', value: review, tone: 'neutral', unavailable: !alertsReady },
            { label: 'Accounts', value: stats?.total_accounts ?? stats?.total_mps ?? '—', unavailable: !statsReady },
            { label: 'Seats', value: seats ?? '—', unavailable: !statsReady || seats === null },
        ];
    }, [alerts, alertsReady, stats, statsReady]);
    return <AdminMetricStrip items={items} />;
}

// ─── Needs attention now — the dominant area ──────────────────────────────
function ActionQueue({ alerts, loading, error, onRetry }) {
    const sorted = useMemo(() => [...alerts].sort((a, b) => {
        const rank = { critical: 0, error: 0, warning: 1, info: 2 };
        return (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3);
    }), [alerts]);
    return (
        <AdminPanel
            title="Needs attention now"
            description="Live operational alerts ordered by severity. Open an item to continue in its account or system context."
            actions={<Link className="btn-secondary" href="/dashboard/staff-access/audit">Audit log</Link>}
        >
            <AdminDataState
                loading={loading}
                error={error}
                empty={!loading && !error && sorted.length === 0}
                emptyTitle="No active operational alerts"
                emptyDescription="All alert checks completed and returned no current issues."
                onRetry={onRetry}
                skeletonRows={5}
            >
                <div className="admin-action-queue">
                    {sorted.slice(0, 8).map((alert, index) => (
                        <Link
                            key={`${alert.type}-${alert.tenant_id || 'global'}-${index}`}
                            href={alertDestination(alert)}
                            className="admin-action-row"
                            data-severity={alert.severity || 'info'}
                        >
                            <span className="admin-action-severity">{severityLabel(alert.severity)}</span>
                            <span className="admin-action-copy">
                                <strong>{alert.title}</strong>
                                <small>{alert.description}</small>
                            </span>
                            <span className="admin-action-scope">
                                {alert.tenant_id ? `Account #${alert.tenant_id}` : 'Platform'}
                            </span>
                            <span aria-hidden="true" className="admin-action-arrow">→</span>
                        </Link>
                    ))}
                </div>
            </AdminDataState>
        </AdminPanel>
    );
}

// ─── Platform readiness ───────────────────────────────────────────────────
// Configuration and messaging state only. The health endpoint exposes no
// uptime, latency or success-rate figures, so none are shown.
function PlatformReadiness({ health, loading, error, onRetry }) {
    const lastWebhook = formatAge(health?.whatsapp?.last_webhook);
    const services = health ? [
        {
            label: 'WhatsApp',
            status: health.whatsapp?.status || 'red',
            detail: health.whatsapp?.reason
                || (lastWebhook ? `Last webhook ${lastWebhook} ago` : 'No webhook observation'),
            href: '/dashboard/system/whatsapp',
        },
        {
            label: 'OpenAI',
            status: health.openai?.status || 'red',
            detail: health.openai?.configured ? 'Configured' : 'Not configured',
            href: '/dashboard/cases-intelligence/engine',
        },
        {
            label: 'Gemini',
            status: health.gemini?.status || 'red',
            detail: health.gemini?.configured ? 'Configured' : 'Not configured',
            href: '/dashboard/cases-intelligence/engine',
        },
    ] : [];
    return (
        <AdminPanel
            title="Platform readiness"
            description="Service configuration and messaging health."
            actions={<Link href="/dashboard/system/health" className="btn-secondary">System health</Link>}
        >
            <AdminDataState loading={loading} error={error} onRetry={onRetry} skeletonRows={3}>
                <div className="admin-health-grid">
                    {services.map((service) => (
                        <Link key={service.label} href={service.href} className="admin-health-service">
                            <span className="admin-health-dot" data-status={service.status} />
                            <span>
                                <strong>{service.label}</strong>
                                <small>{service.detail}</small>
                            </span>
                            <span aria-hidden="true">→</span>
                        </Link>
                    ))}
                </div>
            </AdminDataState>
        </AdminPanel>
    );
}

// ─── Platform totals ──────────────────────────────────────────────────────
// Reference figures straight from the reporting endpoint. A field the
// endpoint does not return renders as an em dash, never as zero.
function PlatformTotals({ stats, loading, error, onRetry }) {
    const rows = [
        ['Customer accounts', stats?.total_accounts ?? stats?.total_mps],
        ['MP seats', stats?.mp_seats ?? stats?.lok_sabha],
        ['MLA seats', stats?.mla_seats],
        ['Aspirants', stats?.aspirants],
        ['Profiles', stats?.total_profiles],
        ['Total cases', stats?.total_cases],
    ];
    return (
        <AdminPanel title="Platform totals" description="Current totals from the Admin reporting API.">
            <AdminDataState loading={loading} error={error} onRetry={onRetry} skeletonRows={4}>
                <dl className="admin-activity-list">
                    {rows.map(([label, value]) => (
                        <div key={label}>
                            <dt>{label}</dt>
                            <dd>{value ?? '—'}</dd>
                        </div>
                    ))}
                </dl>
            </AdminDataState>
        </AdminPanel>
    );
}

// ─── Account readiness ────────────────────────────────────────────────────
function AccountReadiness({ accounts, loading, error, onRetry }) {
    const [query, setQuery] = useState('');
    const [filter, setFilter] = useState('all');
    const visible = useMemo(() => accounts.filter((account) => {
        if (filter === 'setup' && (account.completeness || 0) >= 70) return false;
        if (filter === 'whatsapp' && account.whatsapp_number && !String(account.whatsapp_number).startsWith('temp_')) return false;
        const haystack = `${account.display_name || ''} ${account.username || ''} ${account.parliamentary_constituency || ''}`.toLowerCase();
        return !query || haystack.includes(query.toLowerCase());
    }), [accounts, filter, query]);

    return (
        <AdminPanel
            title="Account readiness"
            description="Search customer accounts and continue with the next setup or support action."
            actions={<Link href="/dashboard/accounts/new" className="btn-primary">Create account</Link>}
        >
            <div className="admin-filter-bar">
                <label className="admin-search-field">
                    <span className="sr-only">Search accounts</span>
                    <input
                        className="form-input"
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        placeholder="Search name, seat, or username"
                    />
                </label>
                <div className="admin-filter-pills" aria-label="Account filters">
                    {[['all', 'All'], ['setup', 'Needs setup'], ['whatsapp', 'Missing WhatsApp']].map(([value, label]) => (
                        <button type="button" key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>
                            {label}
                        </button>
                    ))}
                </div>
            </div>
            <AdminDataState
                loading={loading}
                error={error}
                empty={!loading && !error && visible.length === 0}
                emptyTitle="No accounts match this view"
                emptyDescription="Change the search or readiness filter to see other accounts."
                onRetry={onRetry}
                skeletonRows={5}
            >
                <AdminTableWrap label="Account readiness registry">
                    <table className="data-table admin-command-table">
                        <thead>
                            <tr>
                                <th>Account</th><th>Seat</th><th>Stage</th>
                                <th>Profile</th><th>WhatsApp</th><th>Next action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {visible.slice(0, 12).map((account) => {
                                const incomplete = (account.completeness || 0) < 70;
                                const missingWhatsApp = !account.whatsapp_number || String(account.whatsapp_number).startsWith('temp_');
                                return (
                                    <tr key={account.tenant_id}>
                                        <td data-label="Account">
                                            <strong>{account.display_name}</strong>
                                            <small>@{account.username} · #{account.tenant_id}</small>
                                        </td>
                                        <td data-label="Seat">
                                            {account.parliamentary_constituency || 'Not assigned'}
                                            <small>{account.seat_type?.toUpperCase() || account.house || '—'}</small>
                                        </td>
                                        <td data-label="Stage">
                                            <span className={`badge ${account.account_stage === 'aspirant' ? 'badge-amber' : 'badge-green'}`}>
                                                {account.account_stage || 'elected'}
                                            </span>
                                        </td>
                                        <td data-label="Profile"><span className="cn-data">{account.completeness || 0}%</span></td>
                                        <td data-label="WhatsApp">
                                            {missingWhatsApp
                                                ? <span className="badge badge-red">Missing</span>
                                                : <span className="badge badge-green">Configured</span>}
                                        </td>
                                        <td data-label="Next action">
                                            <Link href={incomplete ? `/dashboard/mps/${account.tenant_id}/setup` : `/dashboard/mps/${account.tenant_id}`}>
                                                {incomplete ? 'Continue setup' : 'Open account'} →
                                            </Link>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
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
            const result = await apiGet(path);
            apply(result);
            setState((current) => ({ ...current, [key]: 'ready' }));
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

    const lastChecked = formatAge(health?.last_checked);

    return (
        <div>
            <AdminPageHeader
                context={lastChecked ? `Last checked ${lastChecked} ago` : null}
                title="Command Centre"
                description="Platform readiness and launch blockers."
                actions={(
                    <button
                        className="btn-secondary"
                        type="button"
                        onClick={() => Object.values(loaders).forEach((load) => load())}
                    >
                        Refresh all
                    </button>
                )}
            />

            <AttentionStrip
                stats={stats}
                alerts={alerts}
                alertsReady={state.alerts === 'ready'}
                statsReady={state.stats === 'ready'}
            />

            <ActionQueue
                alerts={alerts}
                loading={state.alerts === 'loading'}
                error={errors.alerts}
                onRetry={loaders.alerts}
            />

            <div className="admin-command-grid">
                <PlatformReadiness
                    health={health}
                    loading={state.health === 'loading'}
                    error={errors.health}
                    onRetry={loaders.health}
                />
                <PlatformTotals
                    stats={stats}
                    loading={state.stats === 'loading'}
                    error={errors.stats}
                    onRetry={loaders.stats}
                />
            </div>

            <AccountReadiness
                accounts={accounts}
                loading={state.accounts === 'loading'}
                error={errors.accounts}
                onRetry={loaders.accounts}
            />
        </div>
    );
}
