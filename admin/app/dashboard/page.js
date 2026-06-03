'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { apiGet } from '@/lib/api';

function HeartbeatIcon({ className = 'h-4 w-4' }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
    );
}

const StatIcons = {
    mps: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
    ),
    lok: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="2" y1="12" x2="22" y2="12" />
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
    ),
    rajya: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
        </svg>
    ),
    profiles: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
        </svg>
    ),
    cases: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
    ),
};

function timeAgo(isoStr) {
    if (!isoStr) return '—';
    const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    return `${Math.floor(diff / 86400)} days ago`;
}

function SystemHealthWidget() {
    const [health, setHealth] = useState(null);

    useEffect(() => {
        apiGet('/api/admin/system-health').then(setHealth).catch(() => {});
    }, []);

    if (!health) return null;

    const services = [
        { key: 'whatsapp', label: 'WhatsApp API', detail: health.whatsapp?.last_webhook ? `Last webhook: ${timeAgo(health.whatsapp.last_webhook)}` : 'No data' },
        { key: 'openai', label: 'OpenAI API', detail: health.openai?.configured ? 'Key configured' : 'Not configured' },
        { key: 'gemini', label: 'Gemini API', detail: health.gemini?.configured ? 'Key configured' : 'Not configured' },
    ];

    const statusTone = {
        green: 'bg-emerald-500',
        amber: 'bg-amber-500',
        red: 'bg-red-500',
    };

    return (
        <div className="rounded-[10px] border border-[var(--line)] bg-[var(--surface)] p-5 shadow-[var(--shadow-sm)]">
            <div className="mb-4 flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                    <div className="flex h-9 w-9 items-center justify-center rounded-[7px] bg-[rgba(11,110,79,0.1)] text-[var(--sansad-green)]">
                        <HeartbeatIcon />
                    </div>
                    <div>
                        <p className="cn-h3">System Health</p>
                        <p className="cn-meta text-xs">Live platform readiness snapshot</p>
                    </div>
                </div>
                <span className="cn-data text-[11px] text-[var(--ink-3)]">Updated {health.last_checked ? timeAgo(health.last_checked) : '—'}</span>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
                {services.map((service) => {
                    const status = health[service.key]?.status || 'red';
                    return (
                        <div key={service.key} className="rounded-[7px] border border-[var(--line)] bg-[var(--surface-2)] px-4 py-3">
                            <div className="mb-1 flex items-center gap-2">
                                <span className={`h-2.5 w-2.5 rounded-full ${statusTone[status] || statusTone.red}`} />
                                <span className="text-sm font-medium text-[var(--ink)]">{service.label}</span>
                            </div>
                            <p className="cn-meta text-xs">{service.detail}</p>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

const ALERT_STYLES = {
    critical: { border: '#fecaca', bg: '#fff1f2', text: '#be123c', label: 'Critical' },
    warning: { border: '#fed7aa', bg: '#fff7ed', text: '#c2410c', label: 'Warning' },
    info: { border: '#bfdbfe', bg: '#eff6ff', text: '#1d4ed8', label: 'Info' },
};

function alertHref(alert) {
    if (alert.tenant_id) {
        if (alert.type === 'setup_incomplete') return `/dashboard/mps/${alert.tenant_id}/setup`;
        if (alert.type === 'low_completeness') return `/dashboard/accounts/registry?tenant_id=${alert.tenant_id}`;
        return `/dashboard/mps/${alert.tenant_id}`;
    }
    if (alert.type === 'expiring_announcement') return '/dashboard/system/announcements';
    return '/dashboard/system/health';
}

function ActionQueue({ alerts, loading, error }) {
    const sortedAlerts = [...alerts].sort((a, b) => {
        const rank = { critical: 0, warning: 1, info: 2 };
        return (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3);
    });

    return (
        <div className="rounded-[10px] border border-[var(--line)] bg-[var(--surface)] p-5 shadow-[var(--shadow-sm)]">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                    <div className="cn-eyebrow">Action Queue</div>
                    <h2 className="cn-h2 mt-2">Operational items needing attention</h2>
                    <p className="cn-meta mt-1">Operational items that need developer attention.</p>
                </div>
                <Link href="/dashboard/staff-access/audit" className="btn-secondary text-sm" style={{ textDecoration: 'none' }}>
                    Audit Log
                </Link>
            </div>

            {error && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">
                    Alerts unavailable: {error}
                </div>
            )}

            {loading ? (
                <div className="grid gap-3 lg:grid-cols-2">
                    {[...Array(4)].map((_, i) => (
                        <div key={i} className="h-[86px] rounded-[7px] border border-[var(--line)] bg-[var(--surface-2)]" />
                    ))}
                </div>
            ) : !error && sortedAlerts.length === 0 ? (
                <div className="rounded-[7px] border border-[rgba(11,110,79,0.16)] bg-[rgba(11,110,79,0.08)] px-4 py-5 text-sm font-semibold text-[var(--sansad-green)]">
                    No active operational alerts.
                </div>
            ) : (
                <div className="grid gap-3 lg:grid-cols-2">
                    {sortedAlerts.slice(0, 6).map((alert, i) => {
                        const tone = ALERT_STYLES[alert.severity] || ALERT_STYLES.info;
                        return (
                            <Link
                                key={`${alert.type}-${alert.tenant_id || 'global'}-${i}`}
                                href={alertHref(alert)}
                                className="block rounded-[7px] border px-4 py-3 transition hover:-translate-y-0.5 hover:shadow-sm"
                                style={{ borderColor: tone.border, background: tone.bg, textDecoration: 'none' }}
                            >
                                <div className="mb-2 flex items-center justify-between gap-3">
                                    <span style={{ color: tone.text }} className="text-[11px] font-bold uppercase tracking-[0.14em]">
                                        {tone.label}
                                    </span>
                                    {alert.tenant_id && (
                                        <span className="cn-data text-[11px] text-[var(--ink-3)]">Tenant #{alert.tenant_id}</span>
                                    )}
                                </div>
                                <div className="text-sm font-bold text-[var(--ink)]">{alert.title}</div>
                                <div className="cn-meta mt-1 text-xs leading-5">{alert.description}</div>
                            </Link>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

function OpsSummary({ alerts, stats, mps }) {
    const blockedLaunches = alerts.filter(a => a.type === 'setup_incomplete').length;
    const staleTenants = alerts.filter(a => a.type === 'tenant_inactive').length;
    const lowCompleteness = alerts.filter(a => a.type === 'low_completeness').length;
    const missingWhatsApp = mps.filter(mp => !mp.whatsapp_number || String(mp.whatsapp_number).startsWith('temp_')).length;
    const items = [
        { label: 'Open Alerts', value: alerts.length, color: '#dc2626' },
        { label: 'Blocked Launches', value: blockedLaunches, color: '#d97706' },
        { label: 'Stale Tenants', value: staleTenants, color: '#7c3aed' },
        { label: 'Low Profiles', value: lowCompleteness, color: '#0891b2' },
        { label: 'Missing WhatsApp', value: missingWhatsApp, color: '#be123c' },
        { label: 'Total Cases', value: stats?.total_cases ?? '—', color: '#006a4d' },
    ];

    return (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            {items.map(item => (
                <div key={item.label} className="rounded-[7px] border border-[var(--line)] bg-[var(--surface)] px-4 py-3 shadow-[var(--shadow-sm)]">
                    <div className="cn-stat text-[24px] leading-none" style={{ color: item.color }}>{item.value}</div>
                    <div className="mt-2 font-[var(--font-mono)] text-[9px] uppercase tracking-[0.12em] text-[var(--ink-3)]">{item.label}</div>
                </div>
            ))}
        </div>
    );
}

function StatCard({ Icon, value, label, accentClass, bgClass }) {
    return (
        <div className="rounded-[10px] border border-[var(--line)] bg-[var(--surface)] p-5 shadow-[var(--shadow-sm)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)]">
            <div className={`mb-3 flex h-10 w-10 items-center justify-center rounded-[7px] ${bgClass} ${accentClass}`}>
                <Icon />
            </div>
            <div className="cn-stat tracking-tight">{value ?? '—'}</div>
            <div className="mt-2 font-[var(--font-mono)] text-[9px] uppercase tracking-[0.12em] text-[var(--ink-3)]">{label}</div>
        </div>
    );
}

function MpCard({ mp }) {
    const initials = mp.display_name.split(' ').slice(0, 2).map((w) => w[0]).join('').toUpperCase();
    const badgeClass = mp.account_stage === 'aspirant' ? 'badge badge-amber' : mp.seat_type === 'mla' ? 'badge badge-red' : 'badge badge-green';
    const badgeLabel = mp.account_stage === 'aspirant' ? `Aspirant ${mp.seat_label || 'MP'}` : (mp.seat_label || (mp.house === 'Lok Sabha' ? 'MP' : 'MP'));
    const fillClass = mp.completeness >= 70 ? 'fill-good' : mp.completeness >= 40 ? 'fill-mid' : 'fill-low';
    const avatarClass = mp.seat_type === 'mla'
        ? 'bg-gradient-to-br from-[#8d153a] to-[#b91c50]'
        : 'bg-gradient-to-br from-[#006a4d] to-[#00875f]';

    return (
        <Link href={`/dashboard/mps/${mp.tenant_id}`} className="block">
            <div className="rounded-[10px] border border-[var(--line)] bg-[var(--surface)] p-4 shadow-[var(--shadow-sm)] transition-all duration-200 hover:-translate-y-0.5 hover:border-[var(--line-2)] hover:shadow-[var(--shadow-md)]">
                <div className="flex items-center gap-3">
                    <div className={`flex h-11 w-11 items-center justify-center rounded-xl text-sm font-bold text-white ${avatarClass}`}>
                        {initials}
                    </div>
                    <div className="min-w-0 flex-1">
                        <div className="mb-1 flex items-center gap-2">
                            <span className="truncate text-sm font-semibold text-[var(--ink)]">{mp.display_name}</span>
                            <span className={badgeClass}>{badgeLabel}</span>
                        </div>
                        <p className="truncate font-[var(--font-mono)] text-[11px] text-[var(--ink-3)]">@{mp.username} · {mp.parliamentary_constituency}</p>
                    </div>
                </div>
                <div className="mt-4 flex items-center gap-3">
                    <div className="completeness-bar flex-1">
                        <div className={`completeness-fill ${fillClass}`} style={{ width: `${mp.completeness || 0}%` }} />
                    </div>
                    <span className="cn-data text-[11px] text-[var(--ink-3)]">{mp.completeness || 0}%</span>
                </div>
            </div>
        </Link>
    );
}

export default function DashboardOverview() {
    const [stats, setStats] = useState(null);
    const [mps, setMps] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [alertsLoading, setAlertsLoading] = useState(true);
    const [alertsError, setAlertsError] = useState('');
    const [search, setSearch] = useState('');
    const [quickFilter, setQuickFilter] = useState('all');

    useEffect(() => {
        apiGet('/api/admin/stats').then(setStats).catch(() => {});
        apiGet('/api/admin/mps').then((r) => setMps(r.mps || [])).catch(() => {});
        apiGet('/api/admin/alerts')
            .then((r) => setAlerts(r.alerts || []))
            .catch((e) => setAlertsError(e.message || 'Failed to load alerts'))
            .finally(() => setAlertsLoading(false));
    }, []);

    const filteredMps = mps
        .filter((m) => {
            if (quickFilter === 'low_completeness') return (m.completeness || 0) < 70;
            if (quickFilter === 'missing_whatsapp') return !m.whatsapp_number || String(m.whatsapp_number).startsWith('temp_');
            if (quickFilter === 'mp_seat') return m.seat_type === 'mp';
            if (quickFilter === 'mla_seat') return m.seat_type === 'mla';
            if (quickFilter === 'aspirants') return m.account_stage === 'aspirant';
            return true;
        })
        .filter((m) => !search || (
            m.display_name.toLowerCase().includes(search.toLowerCase()) ||
            m.username.toLowerCase().includes(search.toLowerCase()) ||
            m.parliamentary_constituency.toLowerCase().includes(search.toLowerCase())
        ));

    const statDefs = stats ? [
        { Icon: StatIcons.mps, value: stats.total_accounts ?? stats.total_mps, label: 'Total Accounts', accentClass: 'text-[#006a4d]', bgClass: 'bg-[#f0fdf4]' },
        { Icon: StatIcons.lok, value: stats.mp_seats ?? stats.lok_sabha, label: 'MP Seats', accentClass: 'text-emerald-600', bgClass: 'bg-[#f0fdf4]' },
        { Icon: StatIcons.rajya, value: stats.mla_seats ?? stats.rajya_sabha, label: 'MLA Seats', accentClass: 'text-[#8d153a]', bgClass: 'bg-[#fff1f2]' },
        { Icon: StatIcons.profiles, value: stats.aspirants ?? 0, label: 'Aspirants', accentClass: 'text-amber-600', bgClass: 'bg-[#fffbeb]' },
        { Icon: StatIcons.profiles, value: stats.total_profiles, label: 'Profiles', accentClass: 'text-amber-600', bgClass: 'bg-[#fffbeb]' },
        { Icon: StatIcons.cases, value: stats.total_cases, label: 'Total Cases', accentClass: 'text-sky-600', bgClass: 'bg-[#f0f9ff]' },
    ] : [];

    return (
        <div className="space-y-6">
            <ActionQueue alerts={alerts} loading={alertsLoading} error={alertsError} />

            <OpsSummary alerts={alerts} stats={stats} mps={mps} />

            <SystemHealthWidget />

            {stats ? (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-6">
                    {statDefs.map((stat) => <StatCard key={stat.label} {...stat} />)}
                </div>
            ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-6">
                    {[...Array(6)].map((_, i) => (
                        <div key={i} className="h-[116px] rounded-[10px] border border-[var(--line)] bg-[var(--surface)] shadow-[var(--shadow-sm)]" />
                    ))}
                </div>
            )}

            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <div className="cn-eyebrow">Tenants</div>
                    <h2 className="cn-h2 mt-2">Political Accounts</h2>
                    <p className="cn-meta mt-1">Search and manage MP, MLA, and aspirant tenant accounts from a unified overview.</p>
                </div>
                <Link href="/dashboard/accounts/new" className="btn-primary">
                    + Add Account
                </Link>
            </div>

            <div className="rounded-[10px] border border-[var(--line)] bg-[var(--surface)] p-4 shadow-[var(--shadow-sm)]">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
                    <div className="search-wrapper flex-1">
                        <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="11" cy="11" r="8" />
                            <line x1="21" y1="21" x2="16.65" y2="16.65" />
                        </svg>
                        <input
                            type="text"
                            className="form-input"
                            placeholder="Search by name, constituency, or username…"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {[
                            ['all', 'All'],
                            ['low_completeness', 'Low profile'],
                            ['missing_whatsapp', 'Missing WhatsApp'],
                            ['mp_seat', 'MP seats'],
                            ['mla_seat', 'MLA seats'],
                            ['aspirants', 'Aspirants'],
                        ].map(([key, label]) => (
                            <button
                                key={key}
                                type="button"
                                onClick={() => setQuickFilter(key)}
                                className={quickFilter === key ? 'btn-primary' : 'btn-secondary'}
                                style={{ padding: '7px 12px', fontSize: '0.76rem' }}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {filteredMps.length === 0 ? (
                <div className="rounded-[10px] border border-dashed border-[var(--line-2)] bg-[var(--surface)] px-6 py-12 text-center shadow-[var(--shadow-sm)]">
                    <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-[10px] bg-[var(--paper-2)] text-[var(--ink-3)]">
                        <StatIcons.mps />
                    </div>
                    <h3 className="cn-h3 text-base">{search ? 'No results found' : 'No accounts registered yet'}</h3>
                    <p className="cn-meta mt-2 text-sm">
                        {search ? `No accounts match "${search}". Try a broader search.` : 'Create the first political account to get started.'}
                    </p>
                </div>
            ) : (
                <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 2xl:grid-cols-3">
                    {filteredMps.map((mp) => <MpCard key={mp.user_id} mp={mp} />)}
                </div>
            )}
        </div>
    );
}
