'use client';

import { useState, useEffect, Fragment } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost } from '@/lib/api';

const CITIZEN_GROUPS = ['Women', 'Farmers', 'SC/ST', 'BPL Families', 'Youth / Students',
    'Senior Citizens', 'Entrepreneurs / MSME', 'Disabled / PwD', 'Rural Residents', 'Urban Residents'];

export default function SchemesPage() {
    const { user } = useAuth();
    const [tab, setTab] = useState('overview');
    const [intelFilter, setIntelFilter] = useState('all'); // 'all' | 'scrutinized' | 'unspent' | 'utilization'
    const [schemes, setSchemes] = useState([]);
    const [data, setData] = useState({});
    const [loading, setLoading] = useState(true);
    const [fundIntel, setFundIntel] = useState(null);
    const [accountability, setAccountability] = useState(null);
    const [expanded, setExpanded] = useState(null);

    // Finder state
    const [query, setQuery] = useState('');
    const [selCategory, setSelCategory] = useState('All');
    const [selMinistry, setSelMinistry] = useState('All');
    const [selFocus, setSelFocus] = useState('All');
    const [searchResults, setSearchResults] = useState(null);
    const [searchLoading, setSearchLoading] = useState(false);

    // Citizen matcher state
    const [citizenGroups, setCitizenGroups] = useState(['BPL Families']);
    const [citizenGender, setCitizenGender] = useState('Any');
    const [citizenLoc, setCitizenLoc] = useState('Any');
    const [citizenResults, setCitizenResults] = useState(null);
    const [citizenLoading, setCitizenLoading] = useState(false);

    const color = user?.theme_color || '#006a4d';

    useEffect(() => {
        async function load() {
            try {
                const [d, fi, acc] = await Promise.all([
                    apiGet('/api/schemes/all'),
                    apiGet('/api/schemes/fund-intel').catch(() => null),
                    apiGet('/api/schemes/accountability').catch(() => null),
                ]);
                setSchemes(d.schemes || []);
                setData(d);
                if (fi && fi.ministries) setFundIntel(fi);
                if (acc && acc.ministries) setAccountability(acc);
            } catch (err) { console.error(err); }
            finally { setLoading(false); }
        }
        load();
    }, []);

    // Scheme Finder search
    const search = async () => {
        if (!query.trim()) { setSearchResults(null); return; }
        setSearchLoading(true);
        try {
            const d = await apiPost('/api/schemes/search', { query });
            setSearchResults(d.schemes || []);
        } catch { setSearchResults([]); }
        finally { setSearchLoading(false); }
    };

    // Filter locally
    const getFilteredSchemes = () => {
        let list = searchResults || schemes;
        if (selCategory !== 'All') list = list.filter(s => s.category === selCategory);
        if (selMinistry !== 'All') list = list.filter(s => (s.ministry || '').includes(selMinistry));
        if (selFocus !== 'All') list = list.filter(s => s.focus === selFocus);
        return list;
    };

    // Citizen match
    const matchCitizen = async () => {
        if (!citizenGroups.length) return;
        setCitizenLoading(true);
        try {
            const d = await apiPost('/api/schemes/citizen-match', {
                groups: citizenGroups, gender: citizenGender, location: citizenLoc
            });
            setCitizenResults(d);
        } catch { setCitizenResults({ schemes: [], total: 0, profile: '' }); }
        finally { setCitizenLoading(false); }
    };

    const toggleGroup = (g) => {
        setCitizenGroups(prev => prev.includes(g) ? prev.filter(x => x !== g) : [...prev, g]);
    };

    const stats = data.stats || {};
    const ministrySummary = data.ministry_summary || [];
    const topSchemes = data.top_schemes || [];
    const categories = data.categories || [];
    const ministries = data.ministries || [];
    const focuses = data.focuses || [];

    if (loading) return <div className="text-center py-20 text-gray-500 text-sm">Loading schemes...</div>;

    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-bold text-gray-800">Fund Intelligence HQ</h1>
                <span className="text-xs text-gray-400">Every scheme, every ministry, at your fingertips</span>
            </div>

            {/* Stats bar */}
            <div className="grid grid-cols-3 gap-4">
                {[
                    { label: 'Total Schemes', value: stats.total || 0 },
                    { label: 'Ministries', value: stats.ministries || 0 },
                    { label: 'Total Allocation', value: `₹${(stats.total_budget || 0).toLocaleString('en-IN')} Cr` },
                ].map(s => (
                    <div key={s.label} className="sansad-card">
                        <div className="sansad-card-body text-center py-3">
                            <div className="text-xl font-bold" style={{ color }}>{s.value}</div>
                            <div className="text-[10px] text-gray-500 uppercase">{s.label}</div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Tabs */}
            <div className="sansad-tabs">
                {[
                    { key: 'overview', label: 'Ministry Overview' },
                    { key: 'intel', label: 'Accountability Radar' },
                    { key: 'finder', label: 'Scheme Finder' },
                    { key: 'citizen', label: 'Citizen Matcher' },
                ].map(t => (
                    <button key={t.key}
                        onClick={() => setTab(t.key)}
                        className={`sansad-tab ${tab === t.key ? 'sansad-tab-active' : ''}`}
                        style={tab === t.key ? { color } : {}}>
                        {t.label}
                    </button>
                ))}
            </div>

            {/* TAB 1: Ministry Overview */}
            {tab === 'overview' && (
                <div className="space-y-5">
                    <div className="sansad-card">
                        <div className="sansad-card-header" style={{ background: color }}>Top 10 Ministries by Budget</div>
                        <div className="sansad-card-body">
                            {ministrySummary.slice(0, 10).map((m, i) => {
                                const maxBudget = ministrySummary[0]?.budget || 1;
                                const pct = Math.max(5, (m.budget / maxBudget) * 100);
                                return (
                                    <div key={i} className="py-2 border-b last:border-0" style={{ borderColor: '#eee' }}>
                                        <div className="flex items-center justify-between text-xs mb-1">
                                            <span className="font-medium text-gray-700 truncate" style={{ maxWidth: '60%' }}>
                                                {m.ministry.replace('Ministry of ', '').replace('Ministry for ', '')}
                                            </span>
                                            <span className="font-bold" style={{ color }}>₹{m.budget.toLocaleString('en-IN')} Cr</span>
                                        </div>
                                        <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                                            <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color, opacity: 0.7 }} />
                                        </div>
                                        <div className="text-[10px] text-gray-400 mt-0.5">{m.count} schemes</div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    <div className="sansad-card">
                        <div className="sansad-card-header" style={{ background: '#555' }}>Top 10 Highest-Budget Schemes</div>
                        <table className="sansad-table">
                            <thead><tr><th>#</th><th>Scheme</th><th>Ministry</th><th>Budget</th></tr></thead>
                            <tbody>
                                {topSchemes.map((s, i) => (
                                    <tr key={i}>
                                        <td className="font-mono text-gray-400">{i + 1}</td>
                                        <td className="font-medium" style={{ color }}>{s.name}</td>
                                        <td className="text-xs">{s.ministry?.replace('Ministry of ', '') || '–'}</td>
                                        <td className="font-semibold">{s.budget_allocation || '–'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="sansad-card">
                            <div className="sansad-card-header" style={{ background: color }}>By Category</div>
                            <div className="sansad-card-body">
                                {categories.map(cat => {
                                    const cnt = schemes.filter(s => s.category === cat).length;
                                    return (
                                        <div key={cat} className="flex items-center justify-between text-xs py-1.5 border-b last:border-0" style={{ borderColor: '#eee' }}>
                                            <span className="text-gray-700">{cat}</span>
                                            <span className="sansad-badge" style={{ background: `${color}15`, color }}>{cnt}</span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                        <div className="sansad-card">
                            <div className="sansad-card-header" style={{ background: '#555' }}>By Focus Area</div>
                            <div className="sansad-card-body" style={{ maxHeight: 400, overflowY: 'auto' }}>
                                {focuses.map(f => {
                                    const cnt = schemes.filter(s => s.focus === f).length;
                                    return (
                                        <div key={f} className="flex items-center justify-between text-xs py-1.5 border-b last:border-0" style={{ borderColor: '#eee' }}>
                                            <span className="text-gray-700 truncate" style={{ maxWidth: '70%' }}>{f}</span>
                                            <span className="text-gray-500">{cnt}</span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* TAB: Accountability Radar — BE → RE → Actual expenditure + Parliament scrutiny */}
            {tab === 'intel' && (() => {
                const acc = accountability || {};
                const accMinistries = acc.ministries || [];
                const accMeta = acc.metadata || {};
                const summary = acc.summary || {};
                const currentFY = summary.current_fy || '2024-25';
                const [prevFY, prev2FY] = (() => {
                    const yr = parseInt(currentFY.split('-')[0]);
                    return [`${yr - 1}-${String(yr).slice(-2)}`, `${yr - 2}-${String(yr - 1).slice(-2)}`];
                })();

                // Util color: green ≥ 90%, amber 75–89%, red < 75%, gray null
                const utilColor = pct => pct == null ? '#9ca3af' : pct >= 90 ? '#16a34a' : pct >= 75 ? '#d97706' : '#dc2626';
                const utilLabel = pct => pct == null ? 'No data' : pct >= 90 ? 'On track' : pct >= 75 ? 'Moderate risk' : 'Lapse risk';
                const tagColor = tag => ({ utilization: '#3b82f6', unspent: '#dc2626', allocation: '#8b5cf6', release: '#06b6d4', delay: '#f59e0b' })[tag] || '#6b7280';

                // Filter logic
                const filtered = accMinistries.filter(m => {
                    if (intelFilter === 'lapse') return m.lapse_risk;
                    if (intelFilter === 'high') {
                        const last = m.trend?.find(t => t.fy === prevFY);
                        return last?.util_pct != null && last.util_pct >= 85;
                    }
                    if (intelFilter === 'scrutiny') return (m.parliament_questions || 0) > 0;
                    return true;
                });

                const lapseCount = accMinistries.filter(m => m.lapse_risk).length;
                const totalBE = summary.total_be_cr || accMinistries.reduce((s, m) => s + (m.be_cr || 0), 0);

                if (!accMinistries.length) {
                    return (
                        <div className="text-center py-16 text-gray-400 text-sm">
                            <div className="text-2xl mb-2">📊</div>
                            <div>Accountability data loading...</div>
                            <div className="text-xs mt-1">Check that the backend is running and /api/schemes/accountability responds.</div>
                        </div>
                    );
                }

                return (
                    <div className="space-y-5">
                        {/* Source banner */}
                        <div className="flex items-start gap-3 px-4 py-3 text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg">
                            <span className="text-base mt-0.5">⚠️</span>
                            <div>
                                <strong>Data limitations:</strong> BE/RE from Union Budget documents. Actuals available for FY {prevFY} and earlier (6–9 month lag post year-end).
                                FY {currentFY} actuals not yet published. Figures approximate — refresh via <code className="bg-amber-100 px-1 rounded">scripts/fetch_accountability_data.py</code>.
                                PFMS real-time data and CAG audit paras require separate integration (see below).
                            </div>
                        </div>

                        {/* Top metrics */}
                        <div className="grid grid-cols-4 gap-3">
                            {[
                                { label: `Total BE ${currentFY}`, value: `₹${(totalBE / 1000).toFixed(0)}K Cr`, sub: `${accMinistries.length} ministries tracked` },
                                { label: 'Lapse Risk', value: lapseCount, sub: 'ministries with <80% hist. utilization', alert: lapseCount > 0 },
                                { label: 'Avg Utilization', value: summary.avg_util_last_year_pct != null ? `${summary.avg_util_last_year_pct}%` : '—', sub: `FY ${prevFY} actuals vs RE` },
                                { label: 'Parliament Scrutiny', value: accMinistries.filter(m => m.parliament_questions > 0).length, sub: `ministries questioned in LS 18` },
                            ].map(s => (
                                <div key={s.label} className="sansad-card">
                                    <div className="sansad-card-body text-center py-3">
                                        <div className="text-lg font-bold" style={{ color: s.alert ? '#dc2626' : color }}>{s.value}</div>
                                        <div className="text-[10px] text-gray-500 uppercase">{s.label}</div>
                                        <div className="text-[9px] text-gray-400">{s.sub}</div>
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* Filter pills */}
                        <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs text-gray-400 font-semibold uppercase">Show:</span>
                            {[
                                { key: 'all', label: 'All Ministries' },
                                { key: 'lapse', label: `⚠ Lapse Risk (${lapseCount})` },
                                { key: 'high', label: '✓ High Utilization' },
                                { key: 'scrutiny', label: 'Parliament Scrutinized' },
                            ].map(f => (
                                <button key={f.key} onClick={() => setIntelFilter(f.key)}
                                    className="px-3 py-1 text-[11px] font-semibold border"
                                    style={intelFilter === f.key
                                        ? { background: color, color: '#fff', borderColor: color }
                                        : { borderColor: '#ddd', color: '#555', background: '#fff' }}>
                                    {f.label}
                                </button>
                            ))}
                            <span className="text-xs text-gray-400 ml-auto">{filtered.length} of {accMinistries.length} ministries</span>
                        </div>

                        {/* Ministry cards */}
                        <div className="space-y-2">
                            {filtered.map((m, i) => {
                                const isOpen = expanded === `acc${i}`;
                                const prevTrend = m.trend?.find(t => t.fy === prevFY);
                                const prev2Trend = m.trend?.find(t => t.fy === prev2FY);
                                const curTrend = m.trend?.find(t => t.fy === currentFY);
                                const prevUtil = prevTrend?.util_pct ?? null;
                                const hasScrutiny = (m.parliament_questions || 0) > 0;

                                // BE → RE bar: RE as % of BE
                                const rePct = curTrend?.re_cr && curTrend?.be_cr
                                    ? Math.min(120, (curTrend.re_cr / curTrend.be_cr) * 100)
                                    : (m.re_cr && m.be_cr ? Math.min(120, (m.re_cr / m.be_cr) * 100) : 100);
                                // Actual bar: actual as % of RE (previous year)
                                const actualPct = prevUtil != null ? Math.min(110, prevUtil) : null;

                                const lapseBorderColor = m.lapse_risk ? '#dc2626' : hasScrutiny ? '#f59e0b' : 'transparent';

                                return (
                                    <div key={i} className="sansad-card" style={{ borderLeft: `4px solid ${lapseBorderColor}` }}>
                                        <div className="sansad-card-body py-3">
                                            {/* Header row */}
                                            <div className="flex items-start justify-between cursor-pointer gap-4"
                                                onClick={() => setExpanded(isOpen ? null : `acc${i}`)}>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 flex-wrap mb-2">
                                                        <span className="text-sm font-semibold text-gray-800">
                                                            {m.full_name?.replace('Ministry of ', '').replace('Ministry for ', '') || m.ministry}
                                                        </span>
                                                        {m.lapse_risk && (
                                                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0" style={{ background: '#fef2f2', color: '#dc2626' }}>
                                                                ⚠ Lapse Risk
                                                            </span>
                                                        )}
                                                        {hasScrutiny && (
                                                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0" style={{ background: '#fffbeb', color: '#d97706' }}>
                                                                {m.parliament_questions} Parliament Q{m.parliament_questions > 1 ? 's' : ''}
                                                            </span>
                                                        )}
                                                    </div>

                                                    {/* BE → RE → Actual visualization */}
                                                    <div className="space-y-1">
                                                        {/* BE bar */}
                                                        <div className="flex items-center gap-2 text-[10px]">
                                                            <span className="w-14 text-gray-400 font-mono shrink-0">BE {currentFY.slice(-2)}</span>
                                                            <div className="flex-1 h-3 bg-gray-100 rounded-sm overflow-hidden">
                                                                <div className="h-full rounded-sm" style={{ width: '100%', background: '#e5e7eb' }} />
                                                            </div>
                                                            <span className="w-24 text-right text-gray-600 font-semibold shrink-0">
                                                                ₹{(m.be_cr || 0).toLocaleString('en-IN')} Cr
                                                            </span>
                                                        </div>
                                                        {/* RE bar */}
                                                        <div className="flex items-center gap-2 text-[10px]">
                                                            <span className="w-14 text-gray-400 font-mono shrink-0">RE {currentFY.slice(-2)}</span>
                                                            <div className="flex-1 h-3 bg-gray-100 rounded-sm overflow-hidden">
                                                                <div className="h-full rounded-sm" style={{
                                                                    width: `${rePct}%`,
                                                                    background: rePct < 90 ? '#f59e0b' : color,
                                                                    opacity: 0.7,
                                                                }} />
                                                            </div>
                                                            <span className="w-24 text-right font-semibold shrink-0" style={{ color: rePct < 90 ? '#d97706' : '#374151' }}>
                                                                ₹{(m.re_cr || 0).toLocaleString('en-IN')} Cr
                                                                {rePct < 95 && <span className="ml-1 text-amber-600">↓{(100 - rePct).toFixed(0)}%</span>}
                                                            </span>
                                                        </div>
                                                        {/* Actual bar (previous year) */}
                                                        <div className="flex items-center gap-2 text-[10px]">
                                                            <span className="w-14 text-gray-400 font-mono shrink-0">Actual {prevFY.slice(-2)}</span>
                                                            <div className="flex-1 h-3 bg-gray-100 rounded-sm overflow-hidden">
                                                                {actualPct != null ? (
                                                                    <div className="h-full rounded-sm" style={{
                                                                        width: `${actualPct}%`,
                                                                        background: utilColor(prevUtil),
                                                                        opacity: 0.85,
                                                                    }} />
                                                                ) : (
                                                                    <div className="h-full rounded-sm w-full" style={{ background: '#f3f4f6' }} />
                                                                )}
                                                            </div>
                                                            <span className="w-24 text-right font-semibold shrink-0" style={{ color: utilColor(prevUtil) }}>
                                                                {prevTrend?.actual_cr != null
                                                                    ? `₹${prevTrend.actual_cr.toLocaleString('en-IN')} Cr`
                                                                    : '—'
                                                                }
                                                                {prevUtil != null && (
                                                                    <span className="ml-1">({prevUtil}%)</span>
                                                                )}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>
                                                <span className="text-gray-300 text-xs shrink-0 mt-1">{isOpen ? '▲' : '▼'}</span>
                                            </div>

                                            {/* Expanded panel */}
                                            {isOpen && (
                                                <div className="mt-4 pt-4 border-t space-y-4" style={{ borderColor: '#eee' }}>

                                                    {/* 3-year trend table */}
                                                    <div>
                                                        <div className="text-[10px] text-gray-500 uppercase font-semibold mb-2">3-Year Expenditure Trend</div>
                                                        <table className="w-full text-xs border-collapse">
                                                            <thead>
                                                                <tr className="text-[10px] text-gray-400 uppercase">
                                                                    <th className="text-left py-1 pr-3 font-medium">FY</th>
                                                                    <th className="text-right py-1 px-3 font-medium">BE (Cr)</th>
                                                                    <th className="text-right py-1 px-3 font-medium">RE (Cr)</th>
                                                                    <th className="text-right py-1 px-3 font-medium">Actual (Cr)</th>
                                                                    <th className="text-right py-1 font-medium">Util %</th>
                                                                </tr>
                                                            </thead>
                                                            <tbody>
                                                                {(m.trend || []).map((t, j) => (
                                                                    <tr key={j} className="border-t" style={{ borderColor: '#f0f0f0' }}>
                                                                        <td className="py-1.5 pr-3 font-mono text-gray-500">{t.fy}</td>
                                                                        <td className="py-1.5 px-3 text-right text-gray-600">{t.be_cr?.toLocaleString('en-IN') || '—'}</td>
                                                                        <td className="py-1.5 px-3 text-right text-gray-600">{t.re_cr?.toLocaleString('en-IN') || '—'}</td>
                                                                        <td className="py-1.5 px-3 text-right font-semibold" style={{ color: t.actual_cr ? '#374151' : '#9ca3af' }}>
                                                                            {t.actual_cr?.toLocaleString('en-IN') || (t.fy === currentFY ? 'Pending' : '—')}
                                                                        </td>
                                                                        <td className="py-1.5 text-right font-bold" style={{ color: utilColor(t.util_pct) }}>
                                                                            {t.util_pct != null ? `${t.util_pct}%` : (t.fy === currentFY ? 'Pending' : '—')}
                                                                        </td>
                                                                    </tr>
                                                                ))}
                                                            </tbody>
                                                        </table>
                                                        {m.data_confidence === 'medium' && (
                                                            <div className="text-[9px] text-gray-400 mt-1">* Figures approximate — medium confidence. Refresh for latest.</div>
                                                        )}
                                                    </div>

                                                    {/* Lapse risk reason */}
                                                    {m.lapse_risk && m.lapse_risk_reason && (
                                                        <div className="p-3 text-xs rounded-lg" style={{ background: '#fef2f2', borderLeft: '3px solid #dc2626' }}>
                                                            <div className="font-semibold text-red-700 mb-1">Why Lapse Risk is Flagged</div>
                                                            <div className="text-red-600">{m.lapse_risk_reason}</div>
                                                        </div>
                                                    )}

                                                    {/* Key schemes */}
                                                    {m.top_schemes?.length > 0 && (
                                                        <div>
                                                            <div className="text-[10px] text-gray-500 uppercase font-semibold mb-1.5">Key Schemes Under This Ministry</div>
                                                            <div className="flex gap-1.5 flex-wrap">
                                                                {m.top_schemes.map((s, k) => (
                                                                    <span key={k} className="text-[11px] px-2 py-0.5 rounded-full border" style={{ borderColor: `${color}40`, color, background: `${color}08` }}>
                                                                        {s}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* Parliament scrutiny */}
                                                    {hasScrutiny && (
                                                        <div>
                                                            <div className="text-[10px] text-gray-500 uppercase font-semibold mb-1.5">
                                                                Parliament Scrutiny Signal <span className="normal-case text-gray-400 font-normal">(scrutiny signal, not fund data)</span>
                                                            </div>
                                                            <div className="flex gap-2 flex-wrap mb-2">
                                                                {Object.entries(m.parliament_tag_counts || {})
                                                                    .sort((a, b) => b[1] - a[1])
                                                                    .map(([tag, cnt]) => (
                                                                        <span key={tag} className="text-[11px] font-semibold px-2 py-0.5 rounded" style={{
                                                                            background: tagColor(tag) + '18', color: tagColor(tag)
                                                                        }}>
                                                                            {tag.charAt(0).toUpperCase() + tag.slice(1)}: {cnt}
                                                                        </span>
                                                                    ))
                                                                }
                                                            </div>
                                                            <div className="space-y-1">
                                                                {(m.parliament_questions_list || []).slice(0, 4).map((q, j) => (
                                                                    <div key={j} className="text-xs text-gray-600 flex gap-2 py-1 border-b last:border-0" style={{ borderColor: '#f0f0f0' }}>
                                                                        <span className="text-gray-400 font-mono text-[10px] shrink-0 mt-0.5">{q.date?.slice(0, 7) || '—'}</span>
                                                                        <span>{q.title}</span>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Coming soon section */}
                        <div className="sansad-card">
                            <div className="sansad-card-header" style={{ background: '#374151' }}>
                                Coming Soon — Data Integrations Pending
                            </div>
                            <div className="sansad-card-body">
                                <div className="grid grid-cols-3 gap-4">
                                    {[
                                        {
                                            icon: '🏦',
                                            title: 'PFMS Real-Time Expenditure',
                                            desc: 'Within-year quarterly actuals from Public Financial Management System. Enables Q3 lapse flagging — critical for timely intervention.',
                                            status: 'Needs CGA / MoF coordination. No public API.',
                                        },
                                        {
                                            icon: '📋',
                                            title: 'CAG Para Tracker',
                                            desc: 'Scheme-wise audit objections from Comptroller & Auditor General reports. Flags schemes with active financial irregularities.',
                                            status: 'PDFs available at cag.gov.in. Parsing pipeline in development.',
                                        },
                                        {
                                            icon: '🗺️',
                                            title: 'State-wise Comparison',
                                            desc: 'Which states are underperforming vs national average on CSS implementation. Critical for MP to pressure state government.',
                                            status: 'Available for 15 flagship schemes via data.gov.in. Expanding coverage.',
                                        },
                                    ].map((item, i) => (
                                        <div key={i} className="p-3 border rounded-lg bg-gray-50" style={{ borderColor: '#e5e7eb' }}>
                                            <div className="text-xl mb-2">{item.icon}</div>
                                            <div className="text-xs font-bold text-gray-700 mb-1">{item.title}</div>
                                            <div className="text-[11px] text-gray-500 mb-2">{item.desc}</div>
                                            <div className="text-[10px] text-amber-700 bg-amber-50 px-2 py-1 rounded border border-amber-100">{item.status}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>

                        <div className="text-[10px] text-gray-400 text-right">
                            Expenditure source: Union Budget documents + Open Budgets India (openbudgetsindia.org) ·
                            Parliament Q&A: ePARLib (sansad.in) LS 18 · Updated: {accMeta.last_updated || 'N/A'}
                        </div>
                    </div>
                );
            })()}

            {/* TAB 3: Scheme Finder */}
            {tab === 'finder' && (
                <div className="space-y-4">
                    {/* Figma: Full-width search */}
                    <div className="flex gap-3">
                        <div className="figma-search-wrap flex-1">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
                            </svg>
                            <input type="text" value={query}
                                onChange={e => setQuery(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && search()}
                                placeholder="Search schemes by name or ministry..."
                                className="figma-search" />
                        </div>
                        <button onClick={search} disabled={searchLoading}
                            className="px-5 py-2 text-white text-sm font-bold rounded-lg disabled:opacity-40"
                            style={{ background: color }}>
                            {searchLoading ? 'Searching...' : 'Search'}
                        </button>
                        {searchResults && (
                            <button onClick={() => { setSearchResults(null); setQuery(''); setSelCategory('All'); }}
                                className="px-4 py-2 text-sm border rounded-lg text-gray-500" style={{ borderColor: '#ddd' }}>
                                Clear
                            </button>
                        )}
                    </div>

                    {/* Figma: Category pill filters */}
                    <div className="flex gap-2 flex-wrap">
                        {['All', ...categories.slice(0, 8)].map(cat => (
                            <button key={cat}
                                onClick={() => setSelCategory(cat)}
                                className={`pill-filter ${selCategory === cat ? 'pill-filter-active' : ''}`}
                                style={selCategory === cat && cat !== 'All' ? { background: color, borderColor: color, color: 'white' } : {}}>
                                {cat}
                            </button>
                        ))}
                    </div>

                    {/* Ministry filter (compact) */}
                    <div className="flex gap-3 items-center">
                        <select value={selMinistry} onChange={e => setSelMinistry(e.target.value)}
                            className="px-3 py-1.5 border text-xs rounded-lg" style={{ borderColor: '#ddd' }}>
                            <option value="All">All Ministries</option>
                            {ministries.map(m => <option key={m} value={m}>{m.replace('Ministry of ', '').replace('Ministry for ', '')}</option>)}
                        </select>
                        <select value={selFocus} onChange={e => setSelFocus(e.target.value)}
                            className="px-3 py-1.5 border text-xs rounded-lg" style={{ borderColor: '#ddd' }}>
                            <option value="All">All Focus Areas</option>
                            {focuses.map(f => <option key={f} value={f}>{f}</option>)}
                        </select>
                    </div>

                    {/* Results */}
                    {(() => {
                        const filtered = getFilteredSchemes();
                        return filtered.length === 0 ? (
                            <div className="text-center py-10 text-gray-400 text-sm bg-white border rounded-lg" style={{ borderColor: '#e5e7eb' }}>
                                No schemes found. Try a broader search or reset filters.
                            </div>
                        ) : (
                            <>
                                <p className="text-xs text-gray-400"><strong className="text-gray-600">{filtered.length}</strong> schemes found</p>
                                <div className="grid grid-cols-3 gap-4">
                                    {filtered.slice(0, 30).map((s, i) => (
                                        <div key={s.id || i} className="figma-card flex flex-col gap-3">
                                            <div>
                                                <h3 className="text-sm font-bold text-gray-900 leading-tight">{s.name}</h3>
                                                <p className="text-xs text-gray-500 mt-1">{(s.ministry || '').replace('Ministry of ', '').replace('Ministry for ', '')}</p>
                                            </div>
                                            {s.budget_allocation && (
                                                <p className="text-lg font-bold" style={{ color }}>{s.budget_allocation}</p>
                                            )}
                                            <div className="flex gap-1.5 flex-wrap">
                                                {[s.focus, s.category].filter(Boolean).map(tag => (
                                                    <span key={tag} className="sansad-badge"
                                                        style={{ background: `${color}12`, color, borderRadius: 4, fontSize: 10 }}>
                                                        {tag}
                                                    </span>
                                                ))}
                                            </div>
                                            <div className="mt-auto pt-2 border-t" style={{ borderColor: '#f0f0f0' }}>
                                                <button
                                                    onClick={() => setExpanded(expanded === `f${i}` ? null : `f${i}`)}
                                                    className="figma-btn-outline w-full justify-center"
                                                    style={{ color, borderColor: color }}>
                                                    ↗ View Details
                                                </button>
                                                {expanded === `f${i}` && (
                                                    <div className="mt-3 text-xs text-gray-600 leading-relaxed">
                                                        {s.description || 'No detailed description available.'}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </>
                        );
                    })()}
                </div>
            )}


            {/* TAB 4: Citizen Matcher */}
            {tab === 'citizen' && (
                <div className="space-y-4">
                    <div className="text-sm text-gray-500">Select a citizen's profile and instantly see every scheme they qualify for.</div>

                    <div className="sansad-card">
                        <div className="sansad-card-header" style={{ background: color }}>Citizen Profile</div>
                        <div className="sansad-card-body space-y-4">
                            <div>
                                <label className="block text-xs font-semibold text-gray-500 uppercase mb-2">Citizen belongs to:</label>
                                <div className="flex gap-2 flex-wrap">
                                    {CITIZEN_GROUPS.map(g => (
                                        <button key={g} onClick={() => toggleGroup(g)}
                                            className="px-3 py-1.5 text-xs font-semibold border"
                                            style={citizenGroups.includes(g)
                                                ? { background: color, color: 'white', borderColor: color }
                                                : { borderColor: '#ddd', color: '#555' }}>
                                            {g}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Gender</label>
                                    <div className="flex gap-2">
                                        {['Any', 'Male', 'Female'].map(g => (
                                            <button key={g} onClick={() => setCitizenGender(g)}
                                                className="px-3 py-1.5 text-xs font-semibold border"
                                                style={citizenGender === g
                                                    ? { background: color, color: 'white', borderColor: color }
                                                    : { borderColor: '#ddd', color: '#555' }}>
                                                {g}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Location</label>
                                    <div className="flex gap-2">
                                        {['Any', 'Rural', 'Urban'].map(l => (
                                            <button key={l} onClick={() => setCitizenLoc(l)}
                                                className="px-3 py-1.5 text-xs font-semibold border"
                                                style={citizenLoc === l
                                                    ? { background: color, color: 'white', borderColor: color }
                                                    : { borderColor: '#ddd', color: '#555' }}>
                                                {l}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>
                            <button onClick={matchCitizen} disabled={!citizenGroups.length || citizenLoading}
                                className="w-full py-2.5 text-white text-sm font-semibold disabled:opacity-40" style={{ background: color }}>
                                {citizenLoading ? 'Matching...' : 'Find Eligible Schemes'}
                            </button>
                        </div>
                    </div>

                    {citizenResults && (
                        <div className="space-y-3">
                            <div className="text-sm font-semibold text-gray-700">
                                <strong style={{ color }}>{citizenResults.total}</strong> schemes found for: <strong>{citizenResults.profile}</strong>
                                {citizenGender !== 'Any' && ` | ${citizenGender}`}
                                {citizenLoc !== 'Any' && ` | ${citizenLoc}`}
                            </div>
                            <div className="sansad-card">
                                <table className="sansad-table">
                                    <thead><tr><th>Scheme</th><th>Ministry</th><th>Budget</th><th>Description</th></tr></thead>
                                    <tbody>
                                        {citizenResults.schemes.slice(0, 30).map((s, i) => (
                                            <tr key={i}>
                                                <td className="font-medium" style={{ color }}>{s.name}</td>
                                                <td className="text-xs">{(s.ministry || '').replace('Ministry of ', '').slice(0, 30)}</td>
                                                <td className="font-semibold">{s.budget_allocation || '–'}</td>
                                                <td className="text-xs text-gray-500 max-w-[300px] truncate">{s.description || '–'}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
