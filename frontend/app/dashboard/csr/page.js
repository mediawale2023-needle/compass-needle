'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost } from '@/lib/api';

export default function CSRPage() {
    const { user } = useAuth();
    const [tab, setTab] = useState('companies');
    const [companies, setCompanies] = useState([]);
    const [districts, setDistricts] = useState([]);
    const [sectors, setSectors] = useState([]);
    const [district, setDistrict] = useState('');
    const [sector, setSector] = useState('');
    const [typeFilter, setTypeFilter] = useState('');
    const [violators, setViolators] = useState([]);
    const [proposals, setProposals] = useState({ candidates: [], monitoring: [] });
    const [loading, setLoading] = useState(true);
    const [expanded, setExpanded] = useState(null);
    const [draftLoading, setDraftLoading] = useState(null);
    const [draftContent, setDraftContent] = useState({});
    const [strategicMatches, setStrategicMatches] = useState([]);
    const [matchLoading, setMatchLoading] = useState(false);
    const [dprLoading, setDprLoading] = useState(null);
    const [dprContent, setDprContent] = useState({});
    const color = user?.theme_color || '#006a4d';

    const fetchCompanies = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (district) params.set('district', district);
            if (sector) params.set('sector', sector);
            if (typeFilter) params.set('company_type', typeFilter);
            const data = await apiGet(`/api/csr/companies?${params}`);
            setCompanies(data.companies || []);
            if (!districts.length) setDistricts(data.districts || []);
            if (!sectors.length) setSectors(data.sectors || []);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    const fetchWatchdog = async () => {
        setLoading(true);
        try {
            const params = district ? `?district=${district}` : '';
            const data = await apiGet(`/api/csr/watchdog${params}`);
            setViolators(data.violators || []);
        } catch { }
        finally { setLoading(false); }
    };

    const fetchProposals = async () => {
        setLoading(true);
        try {
            const data = await apiGet('/api/csr/proposals');
            setProposals(data);
        } catch { }
        finally { setLoading(false); }
    };

    const fetchStrategicMatches = async () => {
        setMatchLoading(true);
        try {
            const data = await apiPost('/api/csr/strategic-matches', { district: district || null });
            setStrategicMatches(data.matches || []);
        } catch { setStrategicMatches([]); }
        finally { setMatchLoading(false); }
    };

    const draftLetter = async (company, type) => {
        const key = `${company.Company}_${type}`;
        setDraftLoading(key);
        try {
            const data = await apiPost('/api/csr/draft-letter', {
                company: company.Company,
                district: company.District || district,
                total_3y: company.Total_3Y || '',
                sector: company.Sector || '',
                spend_history: company.Spend_History || company.History || {},
                letter_type: type,
            });
            setDraftContent(prev => ({ ...prev, [key]: data.content }));
        } catch (err) {
            setDraftContent(prev => ({ ...prev, [key]: 'Error generating draft.' }));
        }
        finally { setDraftLoading(null); }
    };

    const generateDPR = async (cluster, company) => {
        const key = `${cluster.category}_${company}`;
        setDprLoading(key);
        try {
            const data = await apiPost('/api/csr/generate-dpr', {
                category: cluster.category,
                area: cluster.area,
                volume: cluster.volume,
                company: company,
                sector: cluster.csr_sector || cluster.category,
            });
            setDprContent(prev => ({ ...prev, [key]: data.content }));
        } catch {
            setDprContent(prev => ({ ...prev, [key]: 'Error generating DPR.' }));
        }
        finally { setDprLoading(null); }
    };

    const downloadText = (text, filename) => {
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename; a.click();
        URL.revokeObjectURL(url);
    };

    useEffect(() => {
        if (tab === 'companies') fetchCompanies();
        else if (tab === 'watchdog') fetchWatchdog();
        else if (tab === 'proposals') fetchProposals();
        else if (tab === 'strategic') fetchStrategicMatches();
    }, [tab]);

    useEffect(() => {
        if (tab === 'companies') fetchCompanies();
    }, [district, sector, typeFilter]);

    const remoteCompanies = companies.filter(c => (c.Type || '').includes('Remote'));
    const localCompanies = companies.filter(c => (c.Type || '').includes('Local'));

    return (
        <div className="space-y-5">
            <h1 className="text-lg font-bold text-gray-800">CSR Intelligence</h1>

            {/* Tabs */}
            <div className="sansad-tabs">
                {[
                    { key: 'companies', label: 'Company Database' },
                    { key: 'watchdog', label: 'Compliance Watchdog' },
                    { key: 'proposals', label: 'CSR Proposals' },
                    { key: 'strategic', label: 'Strategic Matches' },
                ].map(t => (
                    <button key={t.key}
                        onClick={() => setTab(t.key)}
                        className={`sansad-tab ${tab === t.key ? 'sansad-tab-active' : ''}`}
                        style={tab === t.key ? { color } : {}}>
                        {t.label}
                    </button>
                ))}
            </div>

            {/* COMPANY DATABASE */}
            {tab === 'companies' && (
                <div className="space-y-4">
                    <div className="flex gap-3 flex-wrap">
                        <select value={district} onChange={e => setDistrict(e.target.value)}
                            className="px-3 py-2 border text-sm" style={{ borderColor: '#ddd' }}>
                            <option value="">All Districts</option>
                            {districts.map(d => <option key={d} value={d}>{d}</option>)}
                        </select>
                        <select value={sector} onChange={e => setSector(e.target.value)}
                            className="px-3 py-2 border text-sm" style={{ borderColor: '#ddd' }}>
                            <option value="">All Sectors</option>
                            {sectors.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
                            className="px-3 py-2 border text-sm" style={{ borderColor: '#ddd' }}>
                            <option value="">All Types</option>
                            <option value="Remote">Remote Spenders</option>
                            <option value="Local">Local Operations</option>
                        </select>
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                        <div className="sansad-stat" style={{ borderLeftColor: color }}>
                            <div className="text-2xl font-bold text-gray-800">{companies.length}</div>
                            <div className="text-[11px] text-gray-500 uppercase font-semibold mt-1">Companies</div>
                        </div>
                        <div className="sansad-stat" style={{ borderLeftColor: '#1565c0' }}>
                            <div className="text-2xl font-bold text-gray-800">{remoteCompanies.length}</div>
                            <div className="text-[11px] text-gray-500 uppercase font-semibold mt-1">Remote Spenders</div>
                        </div>
                        <div className="sansad-stat" style={{ borderLeftColor: '#f57f17' }}>
                            <div className="text-2xl font-bold text-gray-800">{localCompanies.length}</div>
                            <div className="text-[11px] text-gray-500 uppercase font-semibold mt-1">Local Operations</div>
                        </div>
                    </div>

                    {/* Remote Spenders */}
                    {remoteCompanies.length > 0 && (
                        <div className="sansad-card">
                            <div className="sansad-card-header" style={{ background: '#1565c0' }}>
                                Remote Spenders ({remoteCompanies.length}) — Companies spending without a local office
                            </div>
                            {remoteCompanies.map((c, i) => (
                                <div key={i} className="border-b last:border-0" style={{ borderColor: '#eee' }}>
                                    <div className="px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-gray-50"
                                        onClick={() => setExpanded(expanded === `rem${i}` ? null : `rem${i}`)}>
                                        <div className="flex items-center gap-3">
                                            <span className="text-sm font-semibold text-gray-800">{c.Company}</span>
                                            <span className="sansad-badge" style={{ background: `${color}15`, color }}>{c.Sector}</span>
                                        </div>
                                        <div className="flex items-center gap-4 text-xs">
                                            <span className="font-bold" style={{ color }}>3Y: {c.Total_3Y || 'N/A'}</span>
                                            <span className="text-gray-300">{expanded === `rem${i}` ? '▲' : '▼'}</span>
                                        </div>
                                    </div>
                                    {expanded === `rem${i}` && (
                                        <div className="px-4 pb-4 bg-gray-50 space-y-3">
                                            <div className="grid grid-cols-2 gap-4">
                                                <div>
                                                    <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Spending History</div>
                                                    <div className="space-y-1">
                                                        {Object.entries(c.Spend_History || c.History || {}).map(([yr, amt]) => (
                                                            <div key={yr} className="flex justify-between text-xs text-gray-700 bg-white px-3 py-1.5 border" style={{ borderColor: '#eee' }}>
                                                                <span>{yr}</span>
                                                                <span className="font-semibold">{amt}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                    <div className="text-xs text-gray-500 mt-2">
                                                        <strong>Gap Analysis:</strong> {c.Gap_Analysis || 'N/A'}
                                                    </div>
                                                </div>
                                                <div>
                                                    <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Action</div>
                                                    <button
                                                        onClick={() => draftLetter(c, 'upscale')}
                                                        disabled={draftLoading === `${c.Company}_upscale`}
                                                        className="w-full px-3 py-2 text-white text-xs font-semibold disabled:opacity-40 mb-2"
                                                        style={{ background: color }}>
                                                        {draftLoading === `${c.Company}_upscale` ? 'Drafting...' : 'Draft Upscale Letter'}
                                                    </button>
                                                    {draftContent[`${c.Company}_upscale`] && (
                                                        <div className="space-y-2">
                                                            <pre className="text-xs text-gray-700 bg-white p-3 border max-h-60 overflow-y-auto whitespace-pre-wrap" style={{ borderColor: '#ddd' }}>
                                                                {draftContent[`${c.Company}_upscale`]}
                                                            </pre>
                                                            <button onClick={() => downloadText(draftContent[`${c.Company}_upscale`], `CSR_Upscale_${c.Company}.txt`)}
                                                                className="text-xs px-3 py-1 border" style={{ borderColor: '#ddd', color }}>Download</button>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Local Operations */}
                    {localCompanies.length > 0 && (
                        <div className="sansad-card">
                            <div className="sansad-card-header" style={{ background: '#f57f17', color: '#000' }}>
                                Local Operations ({localCompanies.length})
                            </div>
                            <table className="sansad-table">
                                <thead><tr><th>Company</th><th>Sector</th><th>3-Year Spend</th><th>Status</th></tr></thead>
                                <tbody>
                                    {localCompanies.map((c, i) => (
                                        <tr key={i}>
                                            <td className="font-medium">{c.Company || '–'}</td>
                                            <td>{c.Sector || '–'}</td>
                                            <td className="font-semibold">{c.Total_3Y || '–'}</td>
                                            <td>
                                                <span className={`sansad-badge ${(c.Status || '').includes('ZERO') ? 'status-escalated' : 'status-resolved'}`}>
                                                    {c.Status || '–'}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {loading && <div className="text-center py-10 text-gray-400 text-sm">Loading...</div>}
                    {!loading && companies.length === 0 && (
                        <div className="text-center py-10 text-gray-400 text-sm bg-white border" style={{ borderColor: '#ddd' }}>
                            No CSR companies found. Upload csr_db.json or csr_discovery.json.
                        </div>
                    )}
                </div>
            )}

            {/* COMPLIANCE WATCHDOG */}
            {tab === 'watchdog' && (
                <div className="space-y-4">
                    <div className="text-sm text-gray-500">Companies with local operations but ZERO CSR spend (Section 135 violation).</div>
                    <div className="flex gap-3">
                        <select value={district} onChange={e => setDistrict(e.target.value)}
                            className="px-3 py-2 border text-sm" style={{ borderColor: '#ddd' }}>
                            <option value="">All Districts</option>
                            {districts.map(d => <option key={d} value={d}>{d}</option>)}
                        </select>
                        <button onClick={fetchWatchdog} className="px-4 py-2 text-white text-sm font-semibold" style={{ background: color }}>
                            Check Violations
                        </button>
                    </div>

                    {loading ? (
                        <div className="text-center py-10 text-gray-400 text-sm">Loading...</div>
                    ) : violators.length === 0 ? (
                        <div className="text-sm text-green-800 bg-green-50 px-4 py-3 border border-green-200">
                            No CSR violations found{district ? ` in ${district}` : ''}.
                        </div>
                    ) : (
                        <>
                            <div className="text-sm text-red-800 bg-red-50 px-4 py-3 border border-red-200">
                                {violators.length} companies with ZERO CSR spend despite local operations.
                            </div>
                            <div className="sansad-card">
                                {violators.map((v, i) => (
                                    <div key={i} className="border-b last:border-0" style={{ borderColor: '#eee' }}>
                                        <div className="px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-gray-50"
                                            onClick={() => setExpanded(expanded === `vio${i}` ? null : `vio${i}`)}>
                                            <div className="flex items-center gap-3">
                                                <span className="w-2 h-2 rounded-full bg-red-500"></span>
                                                <span className="text-sm font-semibold text-gray-800">{v.Company}</span>
                                                <span className="text-xs text-gray-500">{v.District}</span>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                <span className="sansad-badge status-escalated">ZERO SPEND</span>
                                                <span className="text-gray-300 text-xs">{expanded === `vio${i}` ? '▲' : '▼'}</span>
                                            </div>
                                        </div>
                                        {expanded === `vio${i}` && (
                                            <div className="px-4 pb-4 bg-red-50 space-y-3">
                                                <div className="grid grid-cols-2 gap-4">
                                                    <div>
                                                        <div className="text-xs font-semibold text-gray-500 uppercase mb-1">3-Year Spending History</div>
                                                        {Object.entries(v.Spend_History || v.History || {}).map(([yr, amt]) => (
                                                            <div key={yr} className="flex justify-between text-xs text-gray-700 bg-white px-3 py-1.5 border mb-1" style={{ borderColor: '#fee' }}>
                                                                <span>{yr}</span>
                                                                <span className="font-semibold text-red-600">{amt}</span>
                                                            </div>
                                                        ))}
                                                        <div className="text-[10px] text-red-600 mt-1">Violation: Section 135 (Local Area Preference)</div>
                                                    </div>
                                                    <div>
                                                        <div className="text-xs font-semibold text-gray-500 uppercase mb-1">Action</div>
                                                        <button
                                                            onClick={() => draftLetter(v, 'show_cause')}
                                                            disabled={draftLoading === `${v.Company}_show_cause`}
                                                            className="w-full px-3 py-2 bg-red-600 text-white text-xs font-semibold disabled:opacity-40 mb-2">
                                                            {draftLoading === `${v.Company}_show_cause` ? 'Drafting...' : 'Draft Show Cause Notice'}
                                                        </button>
                                                        {draftContent[`${v.Company}_show_cause`] && (
                                                            <div className="space-y-2">
                                                                <pre className="text-xs text-gray-700 bg-white p-3 border max-h-60 overflow-y-auto whitespace-pre-wrap" style={{ borderColor: '#ddd' }}>
                                                                    {draftContent[`${v.Company}_show_cause`]}
                                                                </pre>
                                                                <button onClick={() => downloadText(draftContent[`${v.Company}_show_cause`], `Notice_${v.Company}.txt`)}
                                                                    className="text-xs px-3 py-1 border text-red-600" style={{ borderColor: '#fcc' }}>Download</button>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </div>
            )}

            {/* CSR PROPOSALS */}
            {tab === 'proposals' && (
                <div className="space-y-4">
                    {loading ? (
                        <div className="text-center py-10 text-gray-400 text-sm">Loading proposals...</div>
                    ) : (
                        <>
                            <div className="sansad-card">
                                <div className="sansad-card-header" style={{ background: color }}>CSR-Ready Clusters (Qualified for Proposal)</div>
                                <div className="sansad-card-body">
                                    {proposals.candidates?.length > 0 ? (
                                        <div className="space-y-3">
                                            {proposals.candidates.map((c, i) => (
                                                <div key={i} className="border-b last:border-0 pb-3" style={{ borderColor: '#eee' }}>
                                                    <div className="flex items-center justify-between cursor-pointer"
                                                        onClick={() => setExpanded(expanded === `prop${i}` ? null : `prop${i}`)}>
                                                        <div className="flex items-center gap-2">
                                                            <span className={`text-[10px] font-bold px-2 py-0.5 ${c.volume >= 500 ? 'bg-red-100 text-red-700' : c.volume >= 300 ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'}`}>
                                                                {c.volume >= 500 ? 'CRITICAL' : c.volume >= 300 ? 'MAJOR' : 'QUALIFIED'}
                                                            </span>
                                                            <span className="text-sm font-semibold text-gray-800">{c.category} in {c.area}</span>
                                                        </div>
                                                        <div className="flex items-center gap-3">
                                                            <span className="text-xl font-bold text-gray-800">{c.volume}</span>
                                                            <span className="text-[10px] text-gray-400 uppercase">complaints</span>
                                                            <span className="text-gray-300">{expanded === `prop${i}` ? '▲' : '▼'}</span>
                                                        </div>
                                                    </div>
                                                    {expanded === `prop${i}` && (
                                                        <div className="mt-3 pt-3 border-t space-y-3" style={{ borderColor: '#eee' }}>
                                                            <div className="flex gap-4">
                                                                <div className="text-center px-4 py-2 bg-gray-50 border flex-1" style={{ borderColor: '#eee' }}>
                                                                    <div className="text-sm font-bold text-gray-800">{c.volume}</div>
                                                                    <div className="text-[10px] text-gray-500 uppercase">Complaints</div>
                                                                </div>
                                                                <div className="text-center px-4 py-2 bg-gray-50 border flex-1" style={{ borderColor: '#eee' }}>
                                                                    <div className="text-sm font-bold" style={{ color }}>{c.csr_sector || 'General'}</div>
                                                                    <div className="text-[10px] text-gray-500 uppercase">CSR Sector</div>
                                                                </div>
                                                            </div>
                                                            <button
                                                                onClick={() => generateDPR(c, c.category)}
                                                                disabled={dprLoading === `${c.category}_${c.category}`}
                                                                className="w-full px-3 py-2 text-white text-xs font-semibold disabled:opacity-40"
                                                                style={{ background: color }}>
                                                                {dprLoading === `${c.category}_${c.category}` ? 'Generating DPR...' : 'Generate Detailed Project Report (DPR)'}
                                                            </button>
                                                            {dprContent[`${c.category}_${c.category}`] && (
                                                                <div className="space-y-2">
                                                                    <pre className="text-xs text-gray-700 bg-white p-3 border max-h-80 overflow-y-auto whitespace-pre-wrap" style={{ borderColor: '#ddd' }}>
                                                                        {dprContent[`${c.category}_${c.category}`]}
                                                                    </pre>
                                                                    <button onClick={() => downloadText(dprContent[`${c.category}_${c.category}`], `DPR_${c.category}_${c.area}.txt`)}
                                                                        className="text-xs px-3 py-1 border" style={{ borderColor: '#ddd', color }}>Download DPR</button>
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <p className="text-sm text-gray-400">No clusters have reached the threshold yet.</p>
                                    )}
                                </div>
                            </div>

                            <div className="sansad-card">
                                <div className="sansad-card-header" style={{ background: '#555' }}>Monitoring Pipeline</div>
                                <div className="sansad-card-body">
                                    {proposals.monitoring?.length > 0 ? (
                                        <div className="space-y-3">
                                            {proposals.monitoring.map((m, i) => (
                                                <div key={i} className="flex items-center gap-4">
                                                    <div className="flex-1">
                                                        <div className="text-sm font-medium text-gray-700">{m.category} in {m.area}</div>
                                                        <div className="w-full h-3 bg-gray-100 rounded-sm mt-1 overflow-hidden">
                                                            <div className="h-full" style={{ width: `${m.progress_pct}%`, background: color }} />
                                                        </div>
                                                    </div>
                                                    <div className="text-sm font-bold text-gray-600">{m.volume}/200</div>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <p className="text-sm text-gray-400">No clusters approaching the threshold.</p>
                                    )}
                                </div>
                            </div>
                        </>
                    )}
                </div>
            )}

            {/* STRATEGIC MATCHES */}
            {tab === 'strategic' && (
                <div className="space-y-4">
                    <div className="text-sm text-gray-500">
                        Live cross-reference: High-volume grievance clusters matched with CSR-eligible companies by sector.
                    </div>

                    {matchLoading ? (
                        <div className="text-center py-10 text-gray-400 text-sm">Analyzing complaint clusters...</div>
                    ) : strategicMatches.length === 0 ? (
                        <div className="text-sm text-gray-500 bg-gray-50 px-4 py-6 text-center border" style={{ borderColor: '#ddd' }}>
                            No grievance clusters found with 50+ complaints. As more citizen messages come in, strategic matches will appear here.
                        </div>
                    ) : (
                        strategicMatches.map((match, i) => (
                            <div key={i} className="sansad-card">
                                <div className="sansad-card-body">
                                    <div className="flex items-center justify-between mb-3">
                                        <div className="flex items-center gap-2">
                                            <span className={`text-[10px] font-bold px-2 py-0.5 ${match.badge === 'CRITICAL' ? 'bg-red-100 text-red-700' : match.badge === 'MAJOR' ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'}`}>
                                                {match.badge}
                                            </span>
                                            <span className="text-sm font-semibold text-gray-800">{match.category} in {match.area}</span>
                                        </div>
                                        <div className="text-right">
                                            <span className="text-lg font-bold text-gray-800">{match.volume}</span>
                                            <span className="text-[10px] text-gray-400 ml-1">citizen reports</span>
                                        </div>
                                    </div>

                                    {match.matched_companies.length > 0 && (
                                        <div className="space-y-2">
                                            <div className="text-xs font-semibold text-gray-500 uppercase">Matched CSR Companies ({match.matched_sectors.join(', ')})</div>
                                            {match.matched_companies.map((mc, j) => {
                                                const dprKey = `${match.category}_${mc.Company}`;
                                                return (
                                                    <div key={j} className="flex items-center justify-between bg-gray-50 px-3 py-2 border" style={{ borderColor: '#eee' }}>
                                                        <div>
                                                            <span className="text-sm font-medium text-gray-800">{mc.Company}</span>
                                                            <span className="text-xs text-gray-500 ml-2">{mc.Sector} | {mc.Total_3Y || 'N/A'}</span>
                                                        </div>
                                                        <button
                                                            onClick={() => generateDPR(match, mc.Company)}
                                                            disabled={dprLoading === dprKey}
                                                            className="px-3 py-1.5 text-white text-xs font-semibold disabled:opacity-40"
                                                            style={{ background: color }}>
                                                            {dprLoading === dprKey ? 'Generating...' : 'Generate Pitch'}
                                                        </button>
                                                    </div>
                                                );
                                            })}
                                            {/* Show generated DPR content for this match */}
                                            {match.matched_companies.map((mc, j) => {
                                                const dprKey = `${match.category}_${mc.Company}`;
                                                if (!dprContent[dprKey]) return null;
                                                return (
                                                    <div key={`dpr-${j}`} className="space-y-2 mt-2">
                                                        <div className="text-xs font-semibold text-gray-500">Generated Proposal for {mc.Company}</div>
                                                        <pre className="text-xs text-gray-700 bg-white p-3 border max-h-80 overflow-y-auto whitespace-pre-wrap" style={{ borderColor: '#ddd' }}>
                                                            {dprContent[dprKey]}
                                                        </pre>
                                                        <button onClick={() => downloadText(dprContent[dprKey], `Pitch_${mc.Company}_${match.area}.txt`)}
                                                            className="text-xs px-3 py-1 border" style={{ borderColor: '#ddd', color }}>Download</button>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}

                                    {match.matched_companies.length === 0 && (
                                        <div className="text-xs text-gray-400">No matching CSR companies found for this sector.</div>
                                    )}
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
}
