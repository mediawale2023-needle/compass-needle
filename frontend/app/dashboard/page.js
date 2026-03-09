'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';

export default function DashboardPage() {
    const { user } = useAuth();
    const [summary, setSummary] = useState(null);
    const [news, setNews] = useState({ national: [], local: [] });
    const [newsTab, setNewsTab] = useState('national');
    const [parliament, setParliament] = useState(null);
    const [loading, setLoading] = useState(true);

    const color = user?.theme_color || '#006a4d';

    useEffect(() => {
        async function load() {
            try {
                const [sum, nat, loc, parl] = await Promise.all([
                    apiGet('/api/dashboard/summary').catch(() => ({ category_breakdown: {}, status_breakdown: {}, red_zones: [], critical_count: 0 })),
                    apiGet('/api/news?type=national').catch(() => ({ articles: [] })),
                    apiGet('/api/news?type=local').catch(() => ({ articles: [] })),
                    apiGet('/api/parliament/status').catch(() => null),
                ]);
                setSummary(sum);
                setNews({ national: nat.articles || [], local: loc.articles || [] });
                setParliament(parl);
            } catch (err) {
                console.error(err);
                setSummary({ category_breakdown: {}, status_breakdown: {}, red_zones: [], critical_count: 0 });
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    if (loading) return <div className="text-center py-20 text-gray-500 text-sm">Loading dashboard...</div>;

    const cats = summary?.category_breakdown || {};
    const statuses = summary?.status_breakdown || {};
    const totalCases = Object.values(statuses).reduce((a, b) => a + b, 0);
    const maxCat = Math.max(...Object.values(cats), 1);

    const STAT_CARDS = [
        { label: 'TOTAL CASES', value: totalCases, borderColor: color },
        { label: 'NEW / OPEN', value: statuses['new'] || 0, borderColor: '#3b82f6' },
        { label: 'IN PROGRESS', value: statuses['in_progress'] || 0, borderColor: '#f59e0b' },
        { label: 'RESOLVED', value: statuses['resolved'] || 0, borderColor: '#16a34a' },
    ];

    return (
        <div className="space-y-6">
            <h1 className="text-lg font-bold text-gray-900">Dashboard</h1>

            {/* Stat Cards - Figma style: white card with thick left border */}
            <div className="grid grid-cols-4 gap-4">
                {STAT_CARDS.map(({ label, value, borderColor }) => (
                    <div key={label} className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm"
                        style={{ borderLeft: `4px solid ${borderColor}` }}>
                        <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">{label}</div>
                        <div className="text-3xl font-bold text-gray-900">{value}</div>
                    </div>
                ))}
            </div>

            {/* Main content grid: 2/3 + 1/3 */}
            <div className="grid grid-cols-3 gap-5">
                {/* Category Breakdown */}
                <div className="col-span-2 bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-100">
                        <h2 className="text-base font-bold text-gray-900">Category Breakdown</h2>
                    </div>
                    <div className="px-6 py-4">
                        {Object.keys(cats).length > 0 ? (
                            <div className="space-y-4">
                                {Object.entries(cats).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([cat, count]) => {
                                    const pct = Math.round((count / maxCat) * 100);
                                    return (
                                        <div key={cat}>
                                            <div className="flex items-center justify-between mb-1.5">
                                                <span className="text-sm font-medium text-gray-700">{cat}</span>
                                                <span className="text-sm font-bold text-gray-900">{count}</span>
                                            </div>
                                            <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
                                                <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
                                            </div>
                                        </div>
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
                        </div>
                        <div className="px-5 py-3">
                            {summary?.red_zones?.length > 0 ? (
                                <ul className="space-y-2">
                                    {summary.red_zones.map((zone, i) => (
                                        <li key={i} className="flex items-center justify-between py-2 border-b last:border-0 border-gray-50">
                                            <div className="flex items-center gap-2">
                                                <span className="text-red-500 text-base">⚠</span>
                                                <span className="text-sm text-gray-700">{typeof zone === 'string' ? zone : zone.area}</span>
                                            </div>
                                            {typeof zone === 'object' && zone.count && (
                                                <span className="text-sm font-bold text-red-600">{zone.count}</span>
                                            )}
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="text-sm text-green-700 py-2">All areas normal</p>
                            )}
                        </div>
                    </div>

                    {/* News Feed */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                        <div className="px-5 py-4 border-b border-gray-100">
                            <h2 className="text-base font-bold text-gray-900">News Feed</h2>
                        </div>
                        <div className="px-5 py-2 border-b border-gray-100">
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
                                    {(newsTab === 'national' ? news.national : news.local).slice(0, 5).map((a, i) => (
                                        <li key={i}>
                                            <a href={a.link} target="_blank" rel="noopener noreferrer"
                                                className="text-xs text-gray-700 hover:underline leading-snug block">
                                                {a.title}
                                            </a>
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="text-xs text-gray-400 py-2 text-center">No coverage found today</p>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Parliament Status */}
            {parliament && (
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-100">
                        <h2 className="text-base font-bold text-gray-900">Parliament Status</h2>
                    </div>
                    <div className="px-6 py-4">
                        {parliament.in_session ? (
                            <div className="space-y-3">
                                <div className="flex items-center gap-2">
                                    <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse" />
                                    <span className="text-sm font-bold text-green-800">House is in Session — {parliament.session_name}</span>
                                    <span className="text-xs text-gray-400 ml-auto">{parliament.day}, {parliament.date}</span>
                                </div>
                                {parliament.business_items?.length > 0 && (
                                    <ul className="space-y-1">
                                        {parliament.business_items.map((item, i) => (
                                            <li key={i} className="text-xs text-gray-600 bg-gray-50 px-3 py-1.5 rounded border-l-2" style={{ borderLeftColor: color }}>{item}</li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        ) : (
                            <div className="flex items-center gap-2">
                                <span className="w-2.5 h-2.5 rounded-full bg-gray-400" />
                                <span className="text-sm text-gray-600">{parliament.message}</span>
                                {parliament.next_session && (
                                    <span className="text-xs text-gray-400 ml-auto">Next: {parliament.next_session}</span>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
