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
                    apiGet('/api/dashboard/summary'),
                    apiGet('/api/news?type=national').catch(() => ({ articles: [] })),
                    apiGet('/api/news?type=local').catch(() => ({ articles: [] })),
                    apiGet('/api/parliament/status').catch(() => null),
                ]);
                setSummary(sum);
                setNews({ national: nat.articles || [], local: loc.articles || [] });
                setParliament(parl);
            } catch (err) {
                console.error(err);
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

    return (
        <div className="space-y-5">
            {/* Stat row — left-accent cards matching sansad.in style */}
            <div className="grid grid-cols-4 gap-4">
                <div className="sansad-stat" style={{ borderLeftColor: color }}>
                    <div className="text-2xl font-bold text-gray-800">{totalCases}</div>
                    <div className="text-[11px] text-gray-500 uppercase font-semibold mt-1">Total Cases</div>
                </div>
                <div className="sansad-stat" style={{ borderLeftColor: '#1565c0' }}>
                    <div className="text-2xl font-bold text-gray-800">{statuses['new'] || 0}</div>
                    <div className="text-[11px] text-gray-500 uppercase font-semibold mt-1">New / Open</div>
                </div>
                <div className="sansad-stat" style={{ borderLeftColor: '#f57f17' }}>
                    <div className="text-2xl font-bold text-gray-800">{statuses['in_progress'] || 0}</div>
                    <div className="text-[11px] text-gray-500 uppercase font-semibold mt-1">In Progress</div>
                </div>
                <div className="sansad-stat" style={{ borderLeftColor: '#2e7d32' }}>
                    <div className="text-2xl font-bold text-gray-800">{statuses['resolved'] || 0}</div>
                    <div className="text-[11px] text-gray-500 uppercase font-semibold mt-1">Resolved</div>
                </div>
            </div>

            <div className="grid grid-cols-3 gap-5">
                {/* Category Breakdown — sansad card */}
                <div className="col-span-2 sansad-card">
                    <div className="sansad-card-header" style={{ background: color }}>
                        Category Breakdown
                    </div>
                    <div className="sansad-card-body">
                        {Object.keys(cats).length > 0 ? (
                            <table className="sansad-table">
                                <thead>
                                    <tr>
                                        <th>Category</th>
                                        <th style={{ width: '60%' }}>Volume</th>
                                        <th style={{ width: 60, textAlign: 'right' }}>Count</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {Object.entries(cats).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([cat, count]) => {
                                        const max = Math.max(...Object.values(cats));
                                        const pct = Math.round((count / max) * 100);
                                        return (
                                            <tr key={cat}>
                                                <td className="font-medium">{cat}</td>
                                                <td>
                                                    <div className="w-full h-5 bg-gray-100 rounded-sm overflow-hidden">
                                                        <div className="h-full rounded-sm" style={{ width: `${pct}%`, background: color, opacity: 0.8 }} />
                                                    </div>
                                                </td>
                                                <td className="text-right font-semibold">{count}</td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        ) : (
                            <p className="text-gray-400 text-sm py-6 text-center">No data available</p>
                        )}
                    </div>
                </div>

                {/* Right column */}
                <div className="space-y-5">
                    {/* Red Zones */}
                    <div className="sansad-card">
                        <div className="sansad-card-header" style={{ background: '#c62828' }}>
                            Red Zone Alert
                        </div>
                        <div className="sansad-card-body">
                            {summary?.red_zones?.length > 0 ? (
                                <ul className="space-y-1.5">
                                    {summary.red_zones.map((zone, i) => (
                                        <li key={i} className="text-sm text-red-800 bg-red-50 px-3 py-2 border border-red-100">
                                            {zone}
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="text-sm text-green-800 bg-green-50 px-3 py-2 border border-green-100">All areas normal</p>
                            )}
                        </div>
                    </div>

                    {/* Critical */}
                    <div className="sansad-card">
                        <div className="sansad-card-header" style={{ background: color }}>
                            Critical Cases
                        </div>
                        <div className="sansad-card-body text-center py-4">
                            <div className="text-3xl font-bold" style={{ color: summary?.critical_count > 0 ? '#c62828' : color }}>
                                {summary?.critical_count || 0}
                            </div>
                            <div className="text-[11px] text-gray-500 mt-1">flagged as critical</div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Parliament Desk */}
            {parliament && (
                <div className="sansad-card">
                    <div className="sansad-card-header" style={{ background: parliament.in_session ? '#1b5e20' : '#555' }}>
                        Parliament Desk — {parliament.house || 'Lok Sabha'}
                    </div>
                    <div className="sansad-card-body">
                        {parliament.in_session ? (
                            <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse"></span>
                                        <span className="text-sm font-bold text-green-800">House is in Session</span>
                                    </div>
                                    <div className="text-xs text-gray-500">{parliament.day}, {parliament.date}</div>
                                </div>
                                <div className="flex gap-3">
                                    <div className="text-center px-3 py-2 bg-green-50 border border-green-100 flex-1">
                                        <div className="text-sm font-bold text-green-800">{parliament.session_name}</div>
                                        <div className="text-[10px] text-green-600">{parliament.start_date} — {parliament.end_date}</div>
                                    </div>
                                    <div className="text-center px-3 py-2 bg-green-50 border border-green-100">
                                        <div className="text-lg font-bold text-green-800">Day {parliament.session_day}</div>
                                    </div>
                                </div>
                                {parliament.business_items?.length > 0 && (
                                    <div>
                                        <div className="text-[10px] text-gray-500 uppercase font-semibold mb-1">Today's Business</div>
                                        <ul className="space-y-1">
                                            {parliament.business_items.map((item, i) => (
                                                <li key={i} className="text-xs text-gray-700 bg-gray-50 px-3 py-1.5 border" style={{ borderColor: '#eee' }}>
                                                    {item}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                                <a href={parliament.sansad_link} target="_blank" rel="noopener noreferrer"
                                    className="text-[11px] font-semibold hover:underline" style={{ color }}>
                                    View on sansad.in →
                                </a>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                <div className="flex items-center gap-2">
                                    <span className="w-2.5 h-2.5 rounded-full bg-gray-400"></span>
                                    <span className="text-sm font-medium text-gray-600">{parliament.message}</span>
                                </div>
                                {parliament.next_session && (
                                    <div className="text-xs text-gray-500 bg-gray-50 px-3 py-2 border" style={{ borderColor: '#eee' }}>
                                        Next: <strong>{parliament.next_session}</strong> — {parliament.next_session_date}
                                    </div>
                                )}
                                {parliament.next_sitting && (
                                    <div className="text-xs text-gray-500">Next sitting: {parliament.next_sitting}</div>
                                )}
                                <a href={parliament.sansad_link} target="_blank" rel="noopener noreferrer"
                                    className="text-[11px] font-semibold hover:underline" style={{ color }}>
                                    View on sansad.in →
                                </a>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Media Centre */}
            <div className="sansad-card">
                <div className="sansad-card-header" style={{ background: color }}>
                    Media Centre
                </div>
                <div className="px-5 pt-3">
                    <div className="sansad-tabs">
                        {['national', 'local'].map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setNewsTab(tab)}
                                className={`sansad-tab ${newsTab === tab ? 'sansad-tab-active' : ''}`}
                                style={newsTab === tab ? { color } : {}}
                            >
                                {tab === 'national' ? 'National' : 'Local Pulse'}
                            </button>
                        ))}
                    </div>
                </div>
                <div className="sansad-card-body max-h-60 overflow-y-auto">
                    {(newsTab === 'national' ? news.national : news.local).length > 0 ? (
                        <ul className="space-y-2">
                            {(newsTab === 'national' ? news.national : news.local).map((a, i) => (
                                <li key={i}>
                                    <a href={a.link} target="_blank" rel="noopener noreferrer" className="text-sm hover:underline" style={{ color }}>
                                        {a.title}
                                    </a>
                                    {a.source && <span className="text-[11px] text-gray-400 ml-2">{a.source}</span>}
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="text-sm text-gray-400 py-4 text-center">No coverage found today</p>
                    )}
                </div>
            </div>
        </div>
    );
}
