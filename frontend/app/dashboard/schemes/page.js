'use client';

import { useState, useEffect, Fragment } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost } from '@/lib/api';

const CITIZEN_GROUPS = ['Women', 'Farmers', 'SC/ST', 'BPL Families', 'Youth / Students',
    'Senior Citizens', 'Entrepreneurs / MSME', 'Disabled / PwD', 'Rural Residents', 'Urban Residents'];

export default function SchemesPage() {
    const { user } = useAuth();
    const [tab, setTab] = useState('overview');
    const [schemes, setSchemes] = useState([]);
    const [data, setData] = useState({});
    const [loading, setLoading] = useState(true);
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
                const d = await apiGet('/api/schemes/all');
                setSchemes(d.schemes || []);
                setData(d);
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
                    { key: 'radar', label: 'Fund Radar' },
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

            {/* TAB 2: Fund Radar */}
            {tab === 'radar' && (
                <div className="space-y-3">
                    <div className="text-sm text-gray-500">Which ministry has the biggest budget? Click any ministry to see its schemes.</div>
                    {ministrySummary.map((m, i) => (
                        <div key={i} className="sansad-card">
                            <div className="sansad-card-body">
                                <div className="flex items-center justify-between cursor-pointer"
                                    onClick={() => setExpanded(expanded === `r${i}` ? null : `r${i}`)}>
                                    <div className="flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full" style={{
                                            background: m.budget >= 10000 ? '#dc2626' : m.budget >= 1000 ? '#f59e0b' : '#6b7280'
                                        }} />
                                        <span className="text-sm font-semibold text-gray-800">{m.ministry}</span>
                                    </div>
                                    <div className="flex items-center gap-4 text-xs">
                                        <span className="font-bold" style={{ color }}>₹{m.budget.toLocaleString('en-IN')} Cr</span>
                                        <span className="text-gray-400">{m.count} schemes</span>
                                        <span className="text-gray-300">{expanded === `r${i}` ? '▲' : '▼'}</span>
                                    </div>
                                </div>
                                {expanded === `r${i}` && (
                                    <div className="mt-3 pt-3 border-t space-y-2" style={{ borderColor: '#eee' }}>
                                        <div className="flex gap-4 mb-2">
                                            <div className="text-center px-4 py-2 bg-gray-50 border flex-1" style={{ borderColor: '#eee' }}>
                                                <div className="text-sm font-bold" style={{ color }}>₹{m.budget.toLocaleString('en-IN')} Cr</div>
                                                <div className="text-[10px] text-gray-500 uppercase">Total Budget</div>
                                            </div>
                                            <div className="text-center px-4 py-2 bg-gray-50 border flex-1" style={{ borderColor: '#eee' }}>
                                                <div className="text-sm font-bold text-gray-800">{m.count}</div>
                                                <div className="text-[10px] text-gray-500 uppercase">Active Schemes</div>
                                            </div>
                                            <div className="text-center px-4 py-2 bg-gray-50 border flex-1" style={{ borderColor: '#eee' }}>
                                                <div className="text-sm font-bold text-gray-800 truncate">{m.top_scheme?.slice(0, 25)}</div>
                                                <div className="text-[10px] text-gray-500 uppercase">Flagship</div>
                                            </div>
                                        </div>
                                        {schemes.filter(s => s.ministry === m.ministry)
                                            .sort((a, b) => (b.budget_numeric || 0) - (a.budget_numeric || 0))
                                            .map((s, j) => (
                                                <div key={j} className="text-xs text-gray-600 py-1">
                                                    • <strong>{s.name}</strong> — {s.budget_allocation || 'N/A'} | {s.focus || ''}
                                                </div>
                                            ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* TAB 3: Scheme Finder */}
            {tab === 'finder' && (
                <div className="space-y-4">
                    <div className="sansad-card">
                        <div className="sansad-card-header" style={{ background: color }}>Search &amp; Filter</div>
                        <div className="sansad-card-body space-y-3">
                            <div className="flex gap-3">
                                <input type="text" value={query} onChange={e => setQuery(e.target.value)}
                                    onKeyDown={e => e.key === 'Enter' && search()}
                                    placeholder="Search by keyword, e.g., 'water', 'education', 'road'..."
                                    className="flex-1 px-3 py-2.5 border text-sm focus:outline-none" style={{ borderColor: '#ddd' }} />
                                <button onClick={search} disabled={searchLoading}
                                    className="px-5 py-2.5 text-white text-sm font-semibold disabled:opacity-40" style={{ background: color }}>
                                    {searchLoading ? 'Searching...' : 'Search'}
                                </button>
                                {searchResults && (
                                    <button onClick={() => { setSearchResults(null); setQuery(''); }}
                                        className="px-4 py-2.5 text-sm text-gray-500 border" style={{ borderColor: '#ddd' }}>Clear</button>
                                )}
                            </div>
                            <div className="grid grid-cols-3 gap-3">
                                <div>
                                    <label className="block text-[10px] text-gray-500 uppercase mb-1">Ministry</label>
                                    <select value={selMinistry} onChange={e => setSelMinistry(e.target.value)}
                                        className="w-full px-2 py-2 border text-xs" style={{ borderColor: '#ddd' }}>
                                        <option value="All">All Ministries</option>
                                        {ministries.map(m => <option key={m} value={m}>{m.replace('Ministry of ', '')}</option>)}
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-[10px] text-gray-500 uppercase mb-1">Category</label>
                                    <select value={selCategory} onChange={e => setSelCategory(e.target.value)}
                                        className="w-full px-2 py-2 border text-xs" style={{ borderColor: '#ddd' }}>
                                        <option value="All">All Categories</option>
                                        {categories.map(c => <option key={c} value={c}>{c}</option>)}
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-[10px] text-gray-500 uppercase mb-1">Focus</label>
                                    <select value={selFocus} onChange={e => setSelFocus(e.target.value)}
                                        className="w-full px-2 py-2 border text-xs" style={{ borderColor: '#ddd' }}>
                                        <option value="All">All Focus Areas</option>
                                        {focuses.map(f => <option key={f} value={f}>{f}</option>)}
                                    </select>
                                </div>
                            </div>
                        </div>
                    </div>

                    {(() => {
                        const filtered = getFilteredSchemes();
                        return filtered.length === 0 ? (
                            <div className="text-center py-10 text-gray-400 text-sm bg-white border" style={{ borderColor: '#ddd' }}>
                                No schemes found. Try a broader search or reset filters.
                            </div>
                        ) : (
                            <>
                                <div className="text-xs text-gray-500"><strong>{filtered.length}</strong> schemes found</div>
                                <div className="sansad-card">
                                    <table className="sansad-table">
                                        <thead><tr><th>Scheme</th><th>Ministry</th><th>Category</th><th>Focus</th><th>Budget</th></tr></thead>
                                        <tbody>
                                            {filtered.slice(0, 50).map((s, i) => (
                                                <Fragment key={s.id || i}>
                                                    <tr key={s.id || i} onClick={() => setExpanded(expanded === `f${i}` ? null : `f${i}`)} className="cursor-pointer">
                                                        <td className="font-medium" style={{ color }}>{s.name}</td>
                                                        <td className="text-xs">{(s.ministry || '').replace('Ministry of ', '').slice(0, 35)}</td>
                                                        <td><span className="sansad-badge" style={{ background: `${color}15`, color }}>{s.category}</span></td>
                                                        <td className="text-xs text-gray-500">{s.focus || '–'}</td>
                                                        <td className="font-semibold">{s.budget_allocation || '–'}</td>
                                                    </tr>
                                                    {expanded === `f${i}` && (
                                                        <tr key={`fd${i}`}>
                                                            <td colSpan="5" style={{ background: '#fafafa' }}>
                                                                <div className="py-3 space-y-2">
                                                                    <p className="text-sm text-gray-700 leading-relaxed">{s.description || 'No description.'}</p>
                                                                    <div className="flex gap-3 text-xs text-gray-500">
                                                                        <span><strong>Ministry:</strong> {s.ministry}</span>
                                                                        <span><strong>Focus:</strong> {s.focus}</span>
                                                                        <span><strong>Budget:</strong> {s.budget_allocation}</span>
                                                                    </div>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    )}
                                                </Fragment>
                                            ))}
                                        </tbody>
                                    </table>
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
