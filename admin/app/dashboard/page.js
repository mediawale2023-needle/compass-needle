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
        <div className="rounded-2xl border border-[#e2ebe5] bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#006a4d]/10 text-[#006a4d]">
                        <HeartbeatIcon />
                    </div>
                    <div>
                        <p className="text-sm font-semibold text-[#1a2e28]">System Health</p>
                        <p className="text-xs text-[#6b7f76]">Live platform readiness snapshot</p>
                    </div>
                </div>
                <span className="text-xs text-[#6b7f76]">Updated {health.last_checked ? timeAgo(health.last_checked) : '—'}</span>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
                {services.map((service) => {
                    const status = health[service.key]?.status || 'red';
                    return (
                        <div key={service.key} className="rounded-xl border border-[#eef2ef] bg-[#f8faf9] px-4 py-3">
                            <div className="mb-1 flex items-center gap-2">
                                <span className={`h-2.5 w-2.5 rounded-full ${statusTone[status] || statusTone.red}`} />
                                <span className="text-sm font-medium text-[#1a2e28]">{service.label}</span>
                            </div>
                            <p className="text-xs text-[#6b7f76]">{service.detail}</p>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function StatCard({ Icon, value, label, accentClass, bgClass }) {
    return (
        <div className="rounded-2xl border border-[#e2ebe5] bg-white p-5 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md">
            <div className={`mb-3 flex h-10 w-10 items-center justify-center rounded-xl ${bgClass} ${accentClass}`}>
                <Icon />
            </div>
            <div className="text-3xl font-bold tracking-tight text-[#1a2e28]">{value ?? '—'}</div>
            <div className="mt-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#6b7f76]">{label}</div>
        </div>
    );
}

function MpCard({ mp }) {
    const initials = mp.display_name.split(' ').slice(0, 2).map((w) => w[0]).join('').toUpperCase();
    const isLS = mp.house === 'Lok Sabha';
    const badgeClass = isLS ? 'badge badge-green' : 'badge badge-red';
    const badgeLabel = isLS ? 'Lok Sabha' : 'Rajya Sabha';
    const fillClass = mp.completeness >= 70 ? 'fill-good' : mp.completeness >= 40 ? 'fill-mid' : 'fill-low';

    return (
        <Link href={`/dashboard/mps/${mp.tenant_id}`} className="block">
            <div className="rounded-2xl border border-[#e2ebe5] bg-white p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-[#c4d8cc] hover:shadow-md">
                <div className="flex items-center gap-3">
                    <div className={`flex h-11 w-11 items-center justify-center rounded-xl text-sm font-bold text-white ${isLS ? 'bg-gradient-to-br from-[#006a4d] to-[#00875f]' : 'bg-gradient-to-br from-[#8d153a] to-[#b91c50]'}`}>
                        {initials}
                    </div>
                    <div className="min-w-0 flex-1">
                        <div className="mb-1 flex items-center gap-2">
                            <span className="truncate text-sm font-semibold text-[#1a2e28]">{mp.display_name}</span>
                            <span className={badgeClass}>{badgeLabel}</span>
                        </div>
                        <p className="truncate text-xs text-[#6b7f76]">@{mp.username} · {mp.parliamentary_constituency}</p>
                    </div>
                </div>
                <div className="mt-4 flex items-center gap-3">
                    <div className="completeness-bar flex-1">
                        <div className={`completeness-fill ${fillClass}`} style={{ width: `${mp.completeness || 0}%` }} />
                    </div>
                    <span className="text-xs font-semibold text-[#6b7f76]">{mp.completeness || 0}%</span>
                </div>
            </div>
        </Link>
    );
}

export default function DashboardOverview() {
    const [stats, setStats] = useState(null);
    const [mps, setMps] = useState([]);
    const [search, setSearch] = useState('');

    useEffect(() => {
        apiGet('/api/admin/stats').then(setStats).catch(() => {});
        apiGet('/api/admin/mps').then((r) => setMps(r.mps || [])).catch(() => {});
    }, []);

    const filteredMps = search
        ? mps.filter((m) =>
            m.display_name.toLowerCase().includes(search.toLowerCase()) ||
            m.username.toLowerCase().includes(search.toLowerCase()) ||
            m.parliamentary_constituency.toLowerCase().includes(search.toLowerCase())
        )
        : mps;

    const statDefs = stats ? [
        { Icon: StatIcons.mps, value: stats.total_mps, label: 'Total MPs', accentClass: 'text-[#006a4d]', bgClass: 'bg-[#f0fdf4]' },
        { Icon: StatIcons.lok, value: stats.lok_sabha, label: 'Lok Sabha', accentClass: 'text-emerald-600', bgClass: 'bg-[#f0fdf4]' },
        { Icon: StatIcons.rajya, value: stats.rajya_sabha, label: 'Rajya Sabha', accentClass: 'text-[#8d153a]', bgClass: 'bg-[#fff1f2]' },
        { Icon: StatIcons.profiles, value: stats.total_profiles, label: 'Profiles', accentClass: 'text-amber-600', bgClass: 'bg-[#fffbeb]' },
        { Icon: StatIcons.cases, value: stats.total_cases, label: 'Total Cases', accentClass: 'text-sky-600', bgClass: 'bg-[#f0f9ff]' },
    ] : [];

    return (
        <div className="space-y-6">
            <SystemHealthWidget />

            {stats ? (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
                    {statDefs.map((stat) => <StatCard key={stat.label} {...stat} />)}
                </div>
            ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
                    {[...Array(5)].map((_, i) => (
                        <div key={i} className="h-[116px] rounded-2xl border border-[#e2ebe5] bg-white shadow-sm" />
                    ))}
                </div>
            )}

            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-[#1a2e28]">Members of Parliament</h2>
                    <p className="text-sm text-[#6b7f76]">Search and manage tenant accounts from a unified overview.</p>
                </div>
                <Link href="/dashboard/mps/new" className="btn-primary">
                    + Add MP
                </Link>
            </div>

            <div className="rounded-2xl border border-[#e2ebe5] bg-white p-4 shadow-sm">
                <div className="search-wrapper">
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
            </div>

            {filteredMps.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-[#d4e0d9] bg-white px-6 py-12 text-center shadow-sm">
                    <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#f0f4f1] text-[#6b7f76]">
                        <StatIcons.mps />
                    </div>
                    <h3 className="text-base font-semibold text-[#1a2e28]">{search ? 'No results found' : 'No MPs registered yet'}</h3>
                    <p className="mt-2 text-sm text-[#6b7f76]">
                        {search ? `No MPs match "${search}". Try a broader search.` : 'Create the first MP account to get started.'}
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
