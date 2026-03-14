'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

const TYPE_LABELS = {
    draft_letter: 'Letter',
    draft_question: 'PQ',
    analysis: 'Analysis',
    copilot_chat: 'Chat',
};

const QUICK_ACTIONS = [
    {
        label: '+ Log New Case',
        href: '/dashboard/sansadx',
        desc: 'Open Briefcase',
    },
    {
        label: '✉ Upload Letter',
        href: '/dashboard/letterbox',
        desc: 'Scan or upload',
    },
    {
        label: '✍ Draft Response',
        href: '/dashboard/drafter',
        desc: 'AI-assisted writing',
    },
    {
        label: '⊞ Find a Scheme',
        href: '/dashboard/schemes',
        desc: 'Match constituents',
    },
];

function getGreeting() {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
}

function daysAgo(dateStr) {
    if (!dateStr) return null;
    const diff = Date.now() - new Date(dateStr).getTime();
    return Math.floor(diff / (1000 * 60 * 60 * 24));
}

function AgeBadge({ days }) {
    if (days === null) return null;
    const color = days >= 14 ? '#dc2626' : days >= 7 ? '#d97706' : '#16a34a';
    const bg   = days >= 14 ? '#fee2e2' : days >= 7 ? '#fef3c7' : '#dcfce7';
    return (
        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0"
            style={{ color, background: bg }}>
            {days}d
        </span>
    );
}

export default function DashboardPage() {
    const { user } = useAuth();
    const router = useRouter();

    const [summary, setSummary]           = useState(null);
    const [news, setNews]                 = useState({ national: [], local: [] });
    const [newsTab, setNewsTab]           = useState('national');
    const [showNews, setShowNews]         = useState(true);
    const [parliament, setParliament]     = useState(null);
    const [recentActivity, setRecent]     = useState([]);
    const [staleCases, setStaleCases]     = useState([]);
    const [loading, setLoading]           = useState(true);

    const color = user?.theme_color || '#006a4d';

    useEffect(() => {
        async function load() {
            try {
                const [sum, nat, loc, parl, hist, cases] = await Promise.all([
                    apiGet('/api/dashboard/summary').catch(() => ({
                        category_breakdown: {}, status_breakdown: {}, red_zones: [], critical_count: 0,
                    })),
                    apiGet('/api/news?news_type=national').catch(() => ({ articles: [] })),
                    apiGet('/api/news?news_type=local').catch(() => ({ articles: [] })),
                    apiGet('/api/parliament/status').catch(() => null),
                    apiGet('/api/history?limit=5').catch(() => ({ items: [] })),
                    apiGet('/api/cases?page=1&limit=50').catch(() => ({ cases: [] })),
                ]);

                setSummary(sum);
                setNews({ national: nat.articles || [], local: loc.articles || [] });
                setParliament(parl);
                setRecent(hist.items || []);

                // Awaiting Response: cases with status=new (pending initiation), oldest first
                const allCases = cases.cases || cases.items || [];
                const pending = allCases
                    .filter(c => (c.status || '').toLowerCase() === 'new')
                    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
                    .slice(0, 6);
                setStaleCases(pending);
            } catch (err) {
                console.error(err);
                setSummary({ category_breakdown: {}, status_breakdown: {}, red_zones: [], critical_count: 0 });
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    if (loading) return (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
            <div className="w-6 h-6 border-2 border-gray-200 rounded-full animate-spin"
                style={{ borderTopColor: color }} />
            <span className="text-sm text-gray-400">Loading dashboard…</span>
        </div>
    );

    const cats      = summary?.category_breakdown || {};
    const statuses  = summary?.status_breakdown   || {};
    const totalCases = Object.values(statuses).reduce((a, b) => a + b, 0);
    const maxCat    = Math.max(...Object.values(cats), 1);
    const newCount  = statuses['new'] || 0;
    const redCount  = summary?.red_zones?.length  || 0;
    const hasUrgent = newCount > 0 || redCount > 0;
    const isEmpty   = totalCases === 0;

    const STAT_CARDS = [
        { label: 'TOTAL CASES',  value: totalCases,                  borderColor: color,      filter: ''            },
        { label: 'NEW / OPEN',   value: statuses['new']         || 0, borderColor: '#3b82f6', filter: 'new'         },
        { label: 'IN PROGRESS',  value: statuses['in_progress'] || 0, borderColor: '#f59e0b', filter: 'in_progress' },
        { label: 'RESOLVED',     value: statuses['resolved']    || 0, borderColor: '#16a34a', filter: 'resolved'    },
    ];

    return (
        <div className="space-y-5">

            {/* ── 8. Personalised greeting ── */}
            <div>
                <h1 className="text-lg font-bold text-gray-900">
                    {getGreeting()}, {user?.display_name}
                </h1>
                <p className="text-xs text-gray-500 mt-0.5">
                    {user?.constituency} · {user?.house}
                </p>
            </div>

            {/* ── 5. Parliament Status — moved to top ── */}
            {parliament && (
                <div className={`rounded-xl border shadow-sm ${parliament.in_session ? 'bg-green-50 border-green-200' : 'bg-white border-gray-100'}`}>
                    <div className="px-5 py-3">
                        {parliament.in_session ? (
                            <div className="space-y-2">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse shrink-0" />
                                    <span className="text-sm font-bold text-green-800">
                                        House in Session — {parliament.session_name}
                                    </span>
                                    <span className="text-xs text-gray-400 ml-auto">
                                        {parliament.day}, {parliament.date}
                                    </span>
                                </div>
                                {parliament.business_items?.length > 0 && (
                                    <div className="flex items-center justify-between gap-3 flex-wrap">
                                        <div className="flex flex-wrap gap-1.5">
                                            {parliament.business_items.slice(0, 2).map((item, i) => (
                                                <span key={i} className="text-xs text-green-700 bg-green-100 px-2 py-0.5 rounded">
                                                    {item}
                                                </span>
                                            ))}
                                        </div>
                                        <Link
                                            href={`/dashboard/drafter?topic=${encodeURIComponent(parliament.business_items[0] || '')}`}
                                            className="shrink-0 text-xs font-semibold px-3 py-1.5 rounded text-white"
                                            style={{ background: color }}>
                                            Draft a PQ →
                                        </Link>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="flex items-center gap-2">
                                <span className="w-2.5 h-2.5 rounded-full bg-gray-400 shrink-0" />
                                <span className="text-sm text-gray-600">{parliament.message}</span>
                                {parliament.next_session && (
                                    <span className="text-xs text-gray-400 ml-auto whitespace-nowrap">
                                        Next: {parliament.next_session}
                                    </span>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* ── 1. Needs Attention strip ── */}
            {hasUrgent ? (
                <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-3 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                        <span className="text-red-500 text-lg shrink-0">⚠</span>
                        <p className="text-sm font-semibold text-red-800">
                            {newCount > 0 && `${newCount} new grievance${newCount !== 1 ? 's' : ''} need${newCount === 1 ? 's' : ''} attention`}
                            {newCount > 0 && redCount > 0 && '  ·  '}
                            {redCount > 0 && `${redCount} zone${redCount !== 1 ? 's' : ''} flagged`}
                        </p>
                    </div>
                    <Link
                        href="/dashboard/sansadx?status=new"
                        className="shrink-0 text-xs font-semibold px-3 py-1.5 rounded text-white"
                        style={{ background: '#dc2626' }}>
                        Review Now →
                    </Link>
                </div>
            ) : (
                <div className="rounded-xl border border-green-200 bg-green-50 px-5 py-3 flex items-center gap-3">
                    <span className="text-green-600 text-base shrink-0">✓</span>
                    <span className="text-sm font-semibold text-green-800">
                        All clear — no new escalations today
                    </span>
                </div>
            )}

            {/* ── 10. Empty / first-time state ── */}
            {isEmpty ? (
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm px-8 py-14 text-center">
                    <div className="text-5xl mb-4">🏛</div>
                    <h2 className="text-base font-bold text-gray-800 mb-2">Welcome to Compass Needle</h2>
                    <p className="text-sm text-gray-500 mb-2 max-w-md mx-auto">
                        Your constituency office is ready. Start by uploading a letter from a constituent,
                        logging a new case, or drafting your first parliamentary question.
                    </p>
                    <p className="text-xs text-gray-400 mb-8">
                        Once cases are logged, this dashboard will show you a live summary of your constituency.
                    </p>
                    <div className="flex flex-wrap justify-center gap-3">
                        <Link href="/dashboard/letterbox"
                            className="text-sm font-semibold px-5 py-2.5 rounded-lg text-white"
                            style={{ background: color }}>
                            Upload a Letter
                        </Link>
                        <Link href="/dashboard/sansadx"
                            className="text-sm font-semibold px-5 py-2.5 rounded-lg border"
                            style={{ borderColor: color, color }}>
                            Log a Case
                        </Link>
                        <Link href="/dashboard/drafter"
                            className="text-sm font-semibold px-5 py-2.5 rounded-lg border border-gray-300 text-gray-600">
                            Draft a PQ
                        </Link>
                    </div>
                </div>
            ) : (
                <>
                    {/* ── 3. Quick Actions row ── */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {QUICK_ACTIONS.map(({ label, href, desc }) => (
                            <Link key={href} href={href}
                                className="bg-white rounded-xl border border-gray-100 shadow-sm px-4 py-3 hover:shadow-md transition-shadow text-center block">
                                <div className="text-sm font-semibold" style={{ color }}>{label}</div>
                                <div className="text-[11px] text-gray-400 mt-0.5">{desc}</div>
                            </Link>
                        ))}
                    </div>

                    {/* ── 2. Stat Cards — clickable with link to filtered Briefcase ── */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {STAT_CARDS.map(({ label, value, borderColor, filter }) => {
                            const href = filter
                                ? `/dashboard/sansadx?status=${filter}`
                                : '/dashboard/sansadx';
                            return (
                                <Link key={label} href={href}
                                    className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm hover:shadow-md transition-shadow block group"
                                    style={{ borderLeft: `4px solid ${borderColor}` }}>
                                    <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                                        {label}
                                    </div>
                                    <div className="text-3xl font-bold text-gray-900 group-hover:text-gray-700 transition-colors">
                                        {value}
                                    </div>
                                    <div className="text-[10px] text-gray-400 mt-1.5 group-hover:underline">
                                        View cases →
                                    </div>
                                </Link>
                            );
                        })}
                    </div>

                    {/* ── Main 2/3 + 1/3 grid ── */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

                        {/* ── 9. Category Breakdown — clickable bars ── */}
                        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                            <div className="px-6 py-4 border-b border-gray-100">
                                <h2 className="text-base font-bold text-gray-900">Category Breakdown</h2>
                                <p className="text-[11px] text-gray-400 mt-0.5">
                                    Click any category to view those cases in Briefcase
                                </p>
                            </div>
                            <div className="px-6 py-4">
                                {Object.keys(cats).length > 0 ? (
                                    <div className="space-y-4">
                                        {Object.entries(cats)
                                            .sort((a, b) => b[1] - a[1])
                                            .slice(0, 8)
                                            .map(([cat, count]) => {
                                                const pct = Math.round((count / maxCat) * 100);
                                                return (
                                                    <button
                                                        key={cat}
                                                        className="w-full text-left group cursor-pointer"
                                                        onClick={() => router.push(
                                                            `/dashboard/sansadx?category=${encodeURIComponent(cat)}`
                                                        )}>
                                                        <div className="flex items-center justify-between mb-1.5">
                                                            <span className="text-sm font-medium text-gray-700 group-hover:text-gray-900 transition-colors">
                                                                {cat}
                                                            </span>
                                                            <span className="text-sm font-bold text-gray-900">
                                                                {count}
                                                            </span>
                                                        </div>
                                                        <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
                                                            <div
                                                                className="h-full rounded-full transition-all group-hover:opacity-75"
                                                                style={{ width: `${pct}%`, background: color }}
                                                            />
                                                        </div>
                                                    </button>
                                                );
                                            })}
                                    </div>
                                ) : (
                                    <p className="text-gray-400 text-sm py-6 text-center">No data available</p>
                                )}
                            </div>
                        </div>

                        {/* Right column */}
                        <div className="space-y-4">

                            {/* Red Zones */}
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                                <div className="px-5 py-4 border-b border-gray-100">
                                    <h2 className="text-base font-bold text-gray-900">Red Zones</h2>
                                    <p className="text-[11px] text-gray-400 mt-0.5">
                                        Areas with high grievance concentration
                                    </p>
                                </div>
                                <div className="px-5 py-3">
                                    {summary?.red_zones?.length > 0 ? (
                                        <ul className="space-y-2">
                                            {summary.red_zones.map((zone, i) => (
                                                <li key={i}
                                                    className="flex items-center justify-between py-2 border-b last:border-0 border-gray-50">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-red-500 text-base">⚠</span>
                                                        <span className="text-sm text-gray-700">
                                                            {typeof zone === 'string' ? zone : zone.area}
                                                        </span>
                                                    </div>
                                                    {typeof zone === 'object' && zone.count && (
                                                        <span className="text-sm font-bold text-red-600">
                                                            {zone.count}
                                                        </span>
                                                    )}
                                                </li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <p className="text-sm text-green-700 py-2">All areas normal</p>
                                    )}
                                </div>
                            </div>

                            {/* ── 4. Awaiting Response panel (replaces News Feed) ── */}
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                                <div className="px-5 py-4 border-b border-gray-100">
                                    <h2 className="text-base font-bold text-gray-900">Awaiting Response</h2>
                                    <p className="text-[11px] text-gray-400 mt-0.5">
                                        New cases pending initiation
                                    </p>
                                </div>
                                <div className="px-5 py-3">
                                    {staleCases.length > 0 ? (
                                        <ul className="space-y-0 divide-y divide-gray-50">
                                            {staleCases.map(c => {
                                                const age = daysAgo(c.created_at);
                                                const contact = c.user_phone || c.contact_name || '—';
                                                const category = c.category || '—';
                                                return (
                                                    <li key={c.id}
                                                        className="py-2.5 flex items-start justify-between gap-2 cursor-pointer hover:bg-gray-50 -mx-5 px-5 transition-colors"
                                                        onClick={() => router.push('/dashboard/sansadx?status=new')}>
                                                        <div className="min-w-0">
                                                            <div className="text-[11px] font-bold text-gray-400 uppercase">
                                                                #{c.id}
                                                            </div>
                                                            <div className="text-sm text-gray-800 font-medium truncate">
                                                                {contact}
                                                            </div>
                                                            <div className="text-[11px] text-gray-500 truncate">
                                                                {category}
                                                            </div>
                                                        </div>
                                                        <AgeBadge days={age} />
                                                    </li>
                                                );
                                            })}
                                        </ul>
                                    ) : (
                                        <p className="text-sm text-green-700 py-2 text-center">
                                            All new cases actioned — great work!
                                        </p>
                                    )}
                                </div>
                                <div className="px-5 py-3 border-t border-gray-50">
                                    <Link
                                        href="/dashboard/sansadx?status=new"
                                        className="text-xs font-semibold"
                                        style={{ color }}>
                                        → View all new cases
                                    </Link>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* ── 7. Recent Activity widget ── */}
                    {recentActivity.length > 0 && (
                        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                                <h2 className="text-base font-bold text-gray-900">Recent Activity</h2>
                                <Link href="/dashboard/archives"
                                    className="text-xs font-semibold"
                                    style={{ color }}>
                                    View all →
                                </Link>
                            </div>
                            <div className="divide-y divide-gray-50">
                                {recentActivity.map(item => (
                                    <div key={item.id}
                                        className="px-6 py-3 flex items-center gap-4 hover:bg-gray-50 cursor-pointer transition-colors"
                                        onClick={() => router.push('/dashboard/archives')}>
                                        <span className="w-2 h-2 rounded-full shrink-0"
                                            style={{ background: color }} />
                                        <div className="flex-1 min-w-0 flex items-center gap-2">
                                            <span className="text-[10px] font-bold uppercase shrink-0"
                                                style={{ color }}>
                                                {TYPE_LABELS[item.activity_type] || item.activity_type}
                                            </span>
                                            <span className="text-sm text-gray-700 truncate">
                                                {item.title}
                                            </span>
                                        </div>
                                        <span className="text-[10px] text-gray-400 shrink-0">
                                            {item.created_at
                                                ? new Date(item.created_at).toLocaleString('en-IN', {
                                                    day: '2-digit', month: 'short',
                                                    hour: '2-digit', minute: '2-digit',
                                                })
                                                : '—'}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* ── 4. News Feed — demoted, collapsible ── */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                        <button
                            className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
                            onClick={() => setShowNews(v => !v)}>
                            <h2 className="text-base font-bold text-gray-900">News Feed</h2>
                            <span className="text-xs text-gray-400">{showNews ? '▲ Hide' : '▼ Show'}</span>
                        </button>
                        {showNews && (
                            <>
                                <div className="px-5 py-2 border-t border-b border-gray-100">
                                    <div className="flex gap-4">
                                        {['national', 'local'].map(tab => (
                                            <button key={tab} onClick={() => setNewsTab(tab)}
                                                className="text-xs font-semibold pb-2 transition-colors"
                                                style={newsTab === tab
                                                    ? { color, borderBottom: `2px solid ${color}` }
                                                    : { color: '#9ca3af', borderBottom: '2px solid transparent' }}>
                                                {tab === 'national' ? 'National' : 'Local'}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                                <div className="px-5 py-3 max-h-48 overflow-y-auto">
                                    {(newsTab === 'national' ? news.national : news.local).length > 0 ? (
                                        <ul className="space-y-2">
                                            {(newsTab === 'national' ? news.national : news.local)
                                                .slice(0, 5)
                                                .map((a, i) => (
                                                    <li key={i}>
                                                        <a href={a.link} target="_blank" rel="noopener noreferrer"
                                                            className="text-xs text-gray-700 hover:underline leading-snug block">
                                                            {a.title}
                                                        </a>
                                                    </li>
                                                ))}
                                        </ul>
                                    ) : (
                                        <p className="text-xs text-gray-400 py-2 text-center">
                                            No coverage found today
                                        </p>
                                    )}
                                </div>
                            </>
                        )}
                    </div>
                </>
            )}
        </div>
    );
}
