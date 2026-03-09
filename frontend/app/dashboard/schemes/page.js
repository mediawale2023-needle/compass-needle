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
                const [d, fi] = await Promise.all([
                    apiGet('/api/schemes/all'),
                    apiGet('/api/schemes/fund-intel').catch(() => null),
                ]);
                setSchemes(d.schemes || []);
                setData(d);
                if (fi && fi.ministries) setFundIntel(fi);
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
                    { key: 'intel', label: 'Fund Intelligence' },
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

            {/* TAB: Fund Intelligence (merged Radar + Parliament Scrutiny) */}
            {tab === 'intel' && (() => {
                const meta = fundIntel?.metadata || {};
                const fiMinistries = fundIntel?.ministries || [];

                // Build a lookup from fund intel by normalized ministry name for merging
                const normName = s => s.toUpperCase()
                    .replace(/MINISTRY OF |MINISTRY FOR |DEPARTMENT OF /g, '')
                    .replace(/&/g, 'AND').trim();

                const fiByNorm = {};
                fiMinistries.forEach(m => { fiByNorm[normName(m.ministry)] = m; });

                // Merge ministrySummary (from schemes_db) with fiMinistries (from parliament)
                // Primary list: ministrySummary enriched with fi data
                const mergedList = ministrySummary.map(m => {
                    const key = normName(m.ministry);
                    // Try to match by key or partial match
                    let fi = fiByNorm[key];
                    if (!fi) {
                        const keys = Object.keys(fiByNorm);
                        const partial = keys.find(k => k.includes(key) || key.includes(k));
                        fi = partial ? fiByNorm[partial] : null;
                    }
                    return {
                        ...m,
                        fi_questions: fi?.total_questions || 0,
                        fi_tag_counts: fi?.tag_counts || {},
                        fi_questions_list: (fi?.questions || []).sort((a, b) => (b.date || '').localeCompare(a.date || '')),
                        fi_severity: fi?.severity_score || 0,
                        fi_budget_cr: fi?.budget_cr || 0,
                        fi_schemes: fi?.schemes || [],
                        fi_has_data: !!fi,
                    };
                });

                // Also include fi-only ministries not in ministrySummary
                const coveredNorms = new Set(mergedList.map(m => normName(m.ministry)));
                fiMinistries.forEach(fi => {
                    if (!coveredNorms.has(normName(fi.ministry))) {
                        mergedList.push({
                            ministry: fi.full_name || fi.ministry,
                            budget: fi.budget_cr || 0,
                            count: fi.scheme_count || 0,
                            top_scheme: fi.schemes?.[0]?.name || '',
                            fi_questions: fi.total_questions,
                            fi_tag_counts: fi.tag_counts || {},
                            fi_questions_list: (fi.questions || []).sort((a, b) => (b.date || '').localeCompare(a.date || '')),
                            fi_severity: fi.severity_score || 0,
                            fi_budget_cr: fi.budget_cr || 0,
                            fi_schemes: fi.schemes || [],
                            fi_has_data: true,
                        });
                    }
                });

                mergedList.sort((a, b) => b.budget - a.budget);

                // Filter
                const filtered = mergedList.filter(m => {
                    if (intelFilter === 'scrutinized') return m.fi_questions > 0;
                    if (intelFilter === 'unspent') return (m.fi_tag_counts.unspent || 0) > 0;
                    if (intelFilter === 'utilization') return (m.fi_tag_counts.utilization || 0) > 0;
                    return true;
                });

                const totalBudget = mergedList.reduce((s, m) => s + (m.budget || 0), 0);
                const totalQs = meta.total_fund_questions || fiMinistries.reduce((s, m) => s + m.total_questions, 0);
                const scrutinizedCount = mergedList.filter(m => m.fi_questions > 0).length;

                const severityColor = s => s >= 50 ? '#dc2626' : s >= 25 ? '#f59e0b' : '#6b7280';
                const tagColor = tag => ({ utilization: '#3b82f6', unspent: '#dc2626', allocation: '#8b5cf6', release: '#06b6d4', delay: '#f59e0b' })[tag] || '#6b7280';
                const tagLabel = tag => ({ utilization: 'Utilization', unspent: 'Unspent', allocation: 'Allocation', release: 'Release', budget: 'Budget', delay: 'Delay', general: 'General' })[tag] || tag;

                return (
                    <div className="space-y-5">
                        {/* Top metrics */}
                        <div className="grid grid-cols-4 gap-3">
                            {[
                                { label: 'Total Budget Tracked', value: `₹${(totalBudget / 1000).toFixed(0)}K Cr`, sub: `${mergedList.length} ministries` },
                                { label: 'Parliament Questions', value: totalQs, sub: `FY ${meta.financial_year || '2025-26'} · LS ${meta.lok_sabha || 18}` },
                                { label: 'Under Scrutiny', value: scrutinizedCount, sub: 'ministries questioned by MPs' },
                                { label: 'Unspent Flags', value: mergedList.reduce((s, m) => s + (m.fi_tag_counts.unspent || 0), 0), sub: 'Q&As about unused funds' },
                            ].map(s => (
                                <div key={s.label} className="sansad-card">
                                    <div className="sansad-card-body text-center py-3">
                                        <div className="text-lg font-bold" style={{ color }}>{s.value}</div>
                                        <div className="text-[10px] text-gray-500 uppercase">{s.label}</div>
                                        <div className="text-[9px] text-gray-400">{s.sub}</div>
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* Filter pills */}
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-400 font-semibold uppercase">Filter:</span>
                            {[
                                { key: 'all', label: 'All Ministries' },
                                { key: 'scrutinized', label: 'Parliament Questioned' },
                                { key: 'unspent', label: 'Unspent Fund Flags' },
                                { key: 'utilization', label: 'Utilization Q&As' },
                            ].map(f => (
                                <button key={f.key} onClick={() => setIntelFilter(f.key)}
                                    className="px-3 py-1 text-[11px] font-semibold border"
                                    style={intelFilter === f.key
                                        ? { background: color, color: '#fff', borderColor: color }
                                        : { borderColor: '#ddd', color: '#555', background: '#fff' }}>
                                    {f.label}
                                </button>
                            ))}
                            <span className="text-xs text-gray-400 ml-auto">{filtered.length} ministries</span>
                        </div>

                        {/* Ministry list */}
                        <div className="space-y-2">
                            {filtered.map((m, i) => {
                                const isOpen = expanded === `fi${i}`;
                                const hasPQ = m.fi_questions > 0;
                                const maxBudget = mergedList[0]?.budget || 1;
                                const budgetPct = Math.max(2, (m.budget / maxBudget) * 100);
                                const unspentCount = m.fi_tag_counts.unspent || 0;
                                const utilCount = m.fi_tag_counts.utilization || 0;

                                return (
                                    <div key={i} className="sansad-card" style={{
                                        borderLeft: hasPQ ? `4px solid ${severityColor(m.fi_severity)}` : '4px solid transparent'
                                    }}>
                                        <div className="sansad-card-body py-3">
                                            {/* Header row */}
                                            <div className="flex items-center justify-between cursor-pointer"
                                                onClick={() => setExpanded(isOpen ? null : `fi${i}`)}>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 flex-wrap">
                                                        <span className="text-sm font-semibold text-gray-800 truncate">
                                                            {m.ministry.replace('Ministry of ', '').replace('Ministry for ', '')}
                                                        </span>
                                                        {hasPQ && (
                                                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0" style={{
                                                                background: severityColor(m.fi_severity) + '18',
                                                                color: severityColor(m.fi_severity)
                                                            }}>
                                                                {m.fi_questions} Parliament Q{m.fi_questions > 1 ? 's' : ''}
                                                            </span>
                                                        )}
                                                        {unspentCount > 0 && (
                                                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0" style={{ background: '#fef2f2', color: '#dc2626' }}>
                                                                {unspentCount} Unspent Flag{unspentCount > 1 ? 's' : ''}
                                                            </span>
                                                        )}
                                                    </div>
                                                    {/* Budget bar */}
                                                    <div className="mt-1.5 flex items-center gap-2">
                                                        <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                                            <div className="h-full rounded-full" style={{ width: `${budgetPct}%`, background: color, opacity: 0.65 }} />
                                                        </div>
                                                        <span className="text-[11px] font-bold shrink-0" style={{ color }}>
                                                            ₹{m.budget.toLocaleString('en-IN')} Cr
                                                        </span>
                                                        <span className="text-[10px] text-gray-400 shrink-0">{m.count} schemes</span>
                                                    </div>
                                                </div>
                                                <span className="text-gray-300 ml-4 text-xs">{isOpen ? '▲' : '▼'}</span>
                                            </div>

                                            {/* Expanded panel */}
                                            {isOpen && (
                                                <div className="mt-3 pt-3 border-t space-y-4" style={{ borderColor: '#eee' }}>
                                                    {/* Stats row */}
                                                    <div className="grid grid-cols-3 gap-3">
                                                        <div className="text-center py-2 bg-gray-50 border" style={{ borderColor: '#eee' }}>
                                                            <div className="text-sm font-bold" style={{ color }}>₹{m.budget.toLocaleString('en-IN')} Cr</div>
                                                            <div className="text-[10px] text-gray-500 uppercase">Budget Allocated</div>
                                                            <div className="text-[9px] text-gray-400">{m.count} active schemes</div>
                                                        </div>
                                                        <div className="text-center py-2 bg-gray-50 border" style={{ borderColor: '#eee' }}>
                                                            <div className="text-sm font-bold text-gray-800">{m.fi_questions}</div>
                                                            <div className="text-[10px] text-gray-500 uppercase">Parliament Q&As</div>
                                                            <div className="text-[9px] text-gray-400">MPs raised in LS {meta.lok_sabha || 18}</div>
                                                        </div>
                                                        <div className="text-center py-2 bg-gray-50 border" style={{ borderColor: '#eee' }}>
                                                            <div className="text-sm font-bold" style={{ color: unspentCount > 0 ? '#dc2626' : '#6b7280' }}>
                                                                {unspentCount > 0 ? `${unspentCount} raised` : '—'}
                                                            </div>
                                                            <div className="text-[10px] text-gray-500 uppercase">Unspent / Lapsed</div>
                                                            <div className="text-[9px] text-gray-400">questions about unused funds</div>
                                                        </div>
                                                    </div>

                                                    {/* Tag breakdown */}
                                                    {hasPQ && Object.keys(m.fi_tag_counts).length > 0 && (
                                                        <div>
                                                            <div className="text-[10px] text-gray-500 uppercase font-semibold mb-1.5">What MPs Asked About</div>
                                                            <div className="flex gap-2 flex-wrap">
                                                                {Object.entries(m.fi_tag_counts)
                                                                    .sort((a, b) => b[1] - a[1])
                                                                    .map(([tag, cnt]) => (
                                                                        <span key={tag} className="text-[11px] font-semibold px-2 py-0.5 rounded" style={{
                                                                            background: tagColor(tag) + '18', color: tagColor(tag)
                                                                        }}>
                                                                            {tagLabel(tag)}: {cnt}
                                                                        </span>
                                                                    ))
                                                                }
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* Schemes under this ministry */}
                                                    {(m.fi_schemes.length > 0 || schemes.filter(s => s.ministry === m.ministry).length > 0) && (
                                                        <div>
                                                            <div className="text-[10px] text-gray-500 uppercase font-semibold mb-1.5">Schemes & Allocation</div>
                                                            <div className="space-y-1">
                                                                {(m.fi_schemes.length > 0
                                                                    ? m.fi_schemes
                                                                    : schemes.filter(s => s.ministry === m.ministry)
                                                                        .sort((a, b) => (b.budget_numeric || 0) - (a.budget_numeric || 0))
                                                                        .map(s => ({ name: s.name, budget_allocation: s.budget_allocation, alloc_cr: s.budget_numeric || 0, focus: s.focus }))
                                                                ).slice(0, 8).map((s, j) => (
                                                                    <div key={j} className="flex items-center justify-between text-xs py-1 border-b last:border-0" style={{ borderColor: '#f0f0f0' }}>
                                                                        <span className="text-gray-700 font-medium truncate" style={{ maxWidth: '65%' }}>
                                                                            {s.name}
                                                                        </span>
                                                                        <span className="font-semibold text-gray-600 shrink-0">
                                                                            {s.budget_allocation || (s.alloc_cr > 0 ? `₹${s.alloc_cr.toLocaleString('en-IN')} Cr` : 'N/A')}
                                                                        </span>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* Parliament Q&A list */}
                                                    {m.fi_questions_list.length > 0 && (
                                                        <div>
                                                            <div className="text-[10px] text-gray-500 uppercase font-semibold mb-1.5">Parliament Questions Raised</div>
                                                            <div className="space-y-1.5">
                                                                {m.fi_questions_list.slice(0, 8).map((q, j) => (
                                                                    <div key={j} className="text-xs py-1.5 border-b last:border-0" style={{ borderColor: '#f0f0f0' }}>
                                                                        <div className="flex items-start gap-2">
                                                                            <span className="text-gray-400 shrink-0 font-mono text-[10px] mt-0.5">{q.date?.slice(0, 7) || '—'}</span>
                                                                            <span className="text-gray-700">{q.title}</span>
                                                                        </div>
                                                                        {q.tags && q.tags.filter(t => t !== 'general').length > 0 && (
                                                                            <div className="flex gap-1 mt-1 ml-10">
                                                                                {q.tags.filter(t => t !== 'general').map(t => (
                                                                                    <span key={t} style={{ fontSize: 9, color: tagColor(t), background: tagColor(t) + '15' }}
                                                                                        className="px-1.5 py-0.5 rounded font-bold uppercase">
                                                                                        {t}
                                                                                    </span>
                                                                                ))}
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                ))}
                                                                {m.fi_questions_list.length > 8 && (
                                                                    <div className="text-[10px] text-gray-400 text-right">
                                                                        +{m.fi_questions_list.length - 8} more questions
                                                                    </div>
                                                                )}
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

                        <div className="text-[10px] text-gray-400 text-right">
                            Source: Budget data from Ministry Annual Reports · Parliament Q&A: ePARLib (sansad.in) LS {meta.lok_sabha || 18} · FY {meta.financial_year || '2025-26'} · Updated: {meta.enriched_at || meta.scraped_at || 'N/A'}
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
