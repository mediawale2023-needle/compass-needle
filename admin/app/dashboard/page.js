'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { apiGet } from '@/lib/api';

/* ── System Health Widget ── */
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

    const dotColor = { green: '#22c55e', amber: '#f59e0b', red: '#ef4444' };

    return (
        <div className="glass-panel" style={{ marginBottom: '1.25rem', padding: '1rem 1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#006a4d" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                    </svg>
                    <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1a2e28', letterSpacing: '-0.2px' }}>System Health</span>
                </div>
                <span style={{ fontSize: '0.65rem', color: '#94a3a0' }}>
                    Last checked: {health.last_checked ? timeAgo(health.last_checked) : '—'}
                </span>
            </div>
            <div style={{ display: 'flex', gap: 16 }}>
                {services.map(s => {
                    const status = health[s.key]?.status || 'red';
                    return (
                        <div key={s.key} style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
                            <div style={{
                                width: 10, height: 10, borderRadius: '50%',
                                background: dotColor[status] || dotColor.red,
                                boxShadow: `0 0 6px ${dotColor[status] || dotColor.red}40`,
                                flexShrink: 0,
                            }} />
                            <div>
                                <div style={{ fontSize: '0.76rem', fontWeight: 600, color: '#1a2e28' }}>{s.label}</div>
                                <div style={{ fontSize: '0.66rem', color: '#6b7f76' }}>{s.detail}</div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function timeAgo(isoStr) {
    if (!isoStr) return '—';
    const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    return `${Math.floor(diff / 86400)} days ago`;
}

/* ── Stat Icons ── */
const StatIcons = {
    mps: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
    ),
    lok: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="2" y1="12" x2="22" y2="12"/>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
        </svg>
    ),
    rajya: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
    ),
    ambassador: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
        </svg>
    ),
    profiles: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
        </svg>
    ),
    cases: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
    ),
};

export default function DashboardOverview() {
    const [stats, setStats] = useState(null);
    const [mps, setMps] = useState([]);
    const [search, setSearch] = useState('');

    useEffect(() => {
        apiGet('/api/admin/stats').then(setStats).catch(() => { });
        apiGet('/api/admin/mps').then(r => setMps(r.mps || [])).catch(() => { });
    }, []);

    const filteredMps = search
        ? mps.filter(m =>
            m.display_name.toLowerCase().includes(search.toLowerCase()) ||
            m.username.toLowerCase().includes(search.toLowerCase()) ||
            m.parliamentary_constituency.toLowerCase().includes(search.toLowerCase())
        )
        : mps;

    const STAT_DEFS = stats ? [
        { Icon: StatIcons.mps, value: stats.total_mps, label: 'Total MPs', accent: '#006a4d', bg: '#f0fdf4' },
        { Icon: StatIcons.lok, value: stats.lok_sabha, label: 'Lok Sabha', accent: '#059669', bg: '#f0fdf4' },
        { Icon: StatIcons.rajya, value: stats.rajya_sabha, label: 'Rajya Sabha', accent: '#8d153a', bg: '#fff1f2' },
        { Icon: StatIcons.ambassador, value: stats.total_prs || 0, label: 'Ambassadors', accent: '#2563eb', bg: '#eff6ff' },
        { Icon: StatIcons.profiles, value: stats.total_profiles, label: 'Profiles', accent: '#d97706', bg: '#fffbeb' },
        { Icon: StatIcons.cases, value: stats.total_cases, label: 'Total Cases', accent: '#0891b2', bg: '#f0f9ff' },
    ] : [];

    return (
        <>
            {/* System Health — First thing visible */}
            <SystemHealthWidget />

            {/* Stat Cards */}
            {stats && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginBottom: '1.5rem' }}>
                    {STAT_DEFS.map((s) => (
                        <StatCard key={s.label} {...s} />
                    ))}
                </div>
            )}
            {!stats && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginBottom: '1.5rem' }}>
                    {[...Array(6)].map((_, i) => (
                        <div key={i} className="stat-card skeleton" style={{ height: 88 }} />
                    ))}
                </div>
            )}

            {/* MP Management Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                <div className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>Members of Parliament</div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <Link href="/dashboard/prs/new" className="btn-secondary" style={{ textDecoration: 'none', fontSize: '0.8rem', padding: '7px 14px' }}>
                        + Add Ambassador
                    </Link>
                    <Link href="/dashboard/mps/new" className="btn-primary" style={{ textDecoration: 'none', fontSize: '0.8rem', padding: '7px 14px' }}>
                        + Add MP
                    </Link>
                </div>
            </div>

            {/* Search */}
            <div className="search-wrapper" style={{ marginBottom: '1rem' }}>
                <svg className="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
                <input
                    type="text"
                    className="form-input"
                    placeholder="Search by name, constituency, or username…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                />
            </div>

            {filteredMps.length === 0 ? (
                <div className="glass-panel">
                    <div className="empty-state">
                        <div className="empty-state-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                                <circle cx="9" cy="7" r="4"/>
                            </svg>
                        </div>
                        <div className="empty-state-title">
                            {search ? 'No results found' : 'No MPs registered yet'}
                        </div>
                        <div className="empty-state-desc">
                            {search ? `No MPs match "${search}"` : 'Click "Add MP" to create the first account'}
                        </div>
                    </div>
                </div>
            ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                    {filteredMps.map((mp) => (
                        <MpCard key={mp.user_id} mp={mp} />
                    ))}
                </div>
            )}
        </>
    );
}

function StatCard({ Icon, value, label, accent, bg }) {
    return (
        <div className="stat-card">
            <div style={{
                width: 34, height: 34, borderRadius: 9,
                background: bg, color: accent,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: 10, flexShrink: 0,
            }}>
                <Icon />
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#1a2e28', lineHeight: 1, letterSpacing: '-1px' }}>
                {value ?? '—'}
            </div>
            <div style={{ color: '#6b7f76', fontSize: '0.72rem', fontWeight: 500, marginTop: 5, textTransform: 'uppercase', letterSpacing: '0.7px' }}>
                {label}
            </div>
        </div>
    );
}

function MpCard({ mp }) {
    const isPR = mp.role === 'pr';
    const initials = mp.display_name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
    const isLS = mp.house === 'Lok Sabha';
    const completeness = mp.completeness || 0;
    const fillClass = completeness >= 70 ? 'fill-good' : completeness >= 40 ? 'fill-mid' : 'fill-low';

    let avatarBg = 'linear-gradient(135deg, #374151, #1f2937)';
    let badgeClass = 'badge badge-blue';
    let badgeLabel = 'PR';

    if (!isPR) {
        avatarBg = isLS
            ? 'linear-gradient(135deg, #006a4d, #00875f)'
            : 'linear-gradient(135deg, #8d153a, #b91c50)';
        badgeClass = isLS ? 'badge badge-green' : 'badge badge-red';
        badgeLabel = isLS ? 'Lok Sabha' : 'Rajya Sabha';
    }

    return (
        <Link href={`/dashboard/mps/${mp.tenant_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="mp-card" style={{ cursor: 'pointer' }}>
                <div style={{
                    width: 40, height: 40, borderRadius: 10,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 700, fontSize: '0.9rem', color: 'white', flexShrink: 0,
                    background: avatarBg,
                    letterSpacing: '0.5px',
                }}>
                    {initials}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 2 }}>
                        <span style={{ color: '#1a2e28', fontWeight: 600, fontSize: '0.875rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {mp.display_name}
                        </span>
                        <span className={badgeClass} style={{ flexShrink: 0, fontSize: '0.62rem', padding: '2px 7px' }}>{badgeLabel}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 7, flexWrap: 'nowrap', overflow: 'hidden' }}>
                        <span style={{ color: '#6b7f76', fontSize: '0.73rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            @{mp.username} · {mp.parliamentary_constituency}
                        </span>
                        <span style={{
                            flexShrink: 0, fontSize: '0.63rem', fontWeight: 700,
                            background: '#f0f4f1', color: '#006a4d',
                            borderRadius: 5, padding: '1px 6px', fontFamily: 'monospace',
                            border: '1px solid #d1e8df',
                        }}>
                            #{mp.tenant_id}
                        </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div className="completeness-bar" style={{ flex: 1 }}>
                            <div className={`completeness-fill ${fillClass}`} style={{ width: `${completeness}%` }} />
                        </div>
                        <span style={{ fontSize: '0.68rem', fontWeight: 600, color: completeness >= 70 ? '#059669' : completeness >= 40 ? '#d97706' : '#dc2626', flexShrink: 0 }}>
                            {completeness}%
                        </span>
                    </div>
                </div>
            </div>
        </Link>
    );
}
