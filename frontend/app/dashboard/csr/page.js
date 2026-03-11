'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, AI_TIMEOUT } from '@/lib/api';

const CSR_PILLS = ['All', 'Steel & Mining', 'Information Technology', 'Banking & Finance', 'Healthcare', 'Energy', 'Automobile'];

export default function CSRPage() {
    const { user } = useAuth();
    const color = user?.theme_color || '#006a4d';

    // ─── Live Data State ───
    const [proposals, setProposals] = useState({ candidates: [], monitoring: [] });
    const [strategicMatches, setStrategicMatches] = useState([]);
    const [proposalsLoading, setProposalsLoading] = useState(true);
    const [matchesLoading, setMatchesLoading] = useState(true);

    // ─── Company Database State ───
    const [companies, setCompanies] = useState([]);
    const [search, setSearch] = useState('');
    const [selectedSector, setSelectedSector] = useState('All');
    const [companiesLoading, setCompaniesLoading] = useState(true);

    // ─── Draft / DPR State ───
    const [draftContent, setDraftContent] = useState({});
    const [draftLoading, setDraftLoading] = useState(null);
    const [dprContent, setDprContent] = useState({});
    const [dprLoading, setDprLoading] = useState(null);

    // ─── Tab State ───
    const [activeTab, setActiveTab] = useState('live');

    // ─── Fetch live proposals from grievance data ───
    useEffect(() => {
        (async () => {
            setProposalsLoading(true);
            try {
                const data = await apiGet('/api/csr/proposals');
                setProposals({
                    candidates: data.candidates || [],
                    monitoring: data.monitoring || [],
                });
            } catch (err) { console.error('Proposals fetch failed:', err); }
            finally { setProposalsLoading(false); }
        })();
    }, []);

    // ─── Fetch strategic matches (live gaps ↔ CSR companies) ───
    useEffect(() => {
        (async () => {
            setMatchesLoading(true);
            try {
                const data = await apiPost('/api/csr/strategic-matches', {});
                setStrategicMatches(data.matches || []);
            } catch (err) { console.error('Strategic matches fetch failed:', err); }
            finally { setMatchesLoading(false); }
        })();
    }, []);

    // ─── Fetch CSR company database ───
    const fetchCompanies = async () => {
        setCompaniesLoading(true);
        try {
            const params = new URLSearchParams();
            if (search) params.set('search', search);
            if (selectedSector !== 'All') params.set('sector', selectedSector);
            const data = await apiGet(`/api/csr/companies?${params}`);
            setCompanies(data.companies || []);
        } catch (err) { console.error(err); }
        finally { setCompaniesLoading(false); }
    };
    useEffect(() => { fetchCompanies(); }, [search, selectedSector]);

    // ─── Generate DPR from live data ───
    const generateDPR = async (match, company) => {
        const key = `${match.category}-${company.Company}`;
        setDprLoading(key);
        try {
            const data = await apiPost('/api/csr/generate-dpr', {
                category: match.category,
                area: match.area,
                volume: match.volume,
                company: company.Company,
                sector: company.Sector || '',
            }, { timeout: AI_TIMEOUT, noRetry: true });
            setDprContent(prev => ({ ...prev, [key]: data.content }));
        } catch (err) {
            setDprContent(prev => ({ ...prev, [key]: 'Error generating DPR. Please try again.' }));
        } finally { setDprLoading(null); }
    };

    // ─── Draft letter from company database ───
    const draftLetter = async (company) => {
        setDraftLoading(company.Company);
        try {
            const data = await apiPost('/api/csr/draft-letter', {
                company: company.Company,
                district: company.District || user?.constituency || '',
                sector: company.Sector || '',
                total_3y: company.Total_3Y || '',
                spend_history: company.Spend_History || company.History || {},
                letter_type: 'upscale',
            }, { timeout: AI_TIMEOUT, noRetry: true });
            setDraftContent(prev => ({ ...prev, [company.Company]: data.content }));
        } catch (err) {
            setDraftContent(prev => ({ ...prev, [company.Company]: 'Error generating draft.' }));
        } finally { setDraftLoading(null); }
    };

    const downloadText = (text, filename) => {
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename; a.click();
        URL.revokeObjectURL(url);
    };

    const badgeColor = (badge) => {
        if (badge === 'CRITICAL') return { bg: '#fbe9e7', text: '#c62828' };
        if (badge === 'MAJOR') return { bg: '#fff3e0', text: '#e65100' };
        return { bg: '#e3f2fd', text: '#1565c0' };
    };

    const totalCandidates = proposals.candidates.length;
    const totalMonitoring = proposals.monitoring.length;
    const totalMatches = strategicMatches.length;

    return (
        <div className="space-y-6">
            <h1 className="text-lg font-bold text-gray-900">CSR Intelligence</h1>

            {/* ─── Summary Stats ─── */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="sansad-stat" style={{ borderLeftColor: '#c62828' }}>
                    <div className="text-xs text-gray-500 uppercase font-semibold tracking-wide">CSR-Ready Projects</div>
                    <div className="text-2xl font-bold mt-1" style={{ color: '#c62828' }}>
                        {proposalsLoading ? '...' : totalCandidates}
                    </div>
                    <div className="text-xs text-gray-400 mt-1">200+ verified complaints</div>
                </div>
                <div className="sansad-stat" style={{ borderLeftColor: '#f57f17' }}>
                    <div className="text-xs text-gray-500 uppercase font-semibold tracking-wide">Monitoring</div>
                    <div className="text-2xl font-bold mt-1" style={{ color: '#f57f17' }}>
                        {proposalsLoading ? '...' : totalMonitoring}
                    </div>
                    <div className="text-xs text-gray-400 mt-1">100-199 complaints, approaching threshold</div>
                </div>
                <div className="sansad-stat" style={{ borderLeftColor: color }}>
                    <div className="text-xs text-gray-500 uppercase font-semibold tracking-wide">Strategic Matches</div>
                    <div className="text-2xl font-bold mt-1" style={{ color }}>
                        {matchesLoading ? '...' : totalMatches}
                    </div>
                    <div className="text-xs text-gray-400 mt-1">Live gaps matched to CSR companies</div>
                </div>
            </div>

            {/* ─── Tab Navigation ─── */}
            <div className="sansad-tabs">
                {[
                    { key: 'live', label: `Live Projects (${totalCandidates + totalMonitoring})` },
                    { key: 'matches', label: `Strategic Matches (${totalMatches})` },
                    { key: 'database', label: 'Company Database' },
                ].map(tab => (
                    <button key={tab.key}
                        className={`sansad-tab ${activeTab === tab.key ? 'sansad-tab-active' : ''}`}
                        style={activeTab === tab.key ? { color, borderBottomColor: color } : {}}
                        onClick={() => setActiveTab(tab.key)}>
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* ═══════════════════════════════════════════
                TAB 1: Live Grievance Clusters → CSR Projects
               ═══════════════════════════════════════════ */}
            {activeTab === 'live' && (
                <div className="space-y-4 animate-fade-in">
                    {proposalsLoading ? (
                        <div className="text-center py-10 text-gray-400 text-sm">Loading live grievance data...</div>
                    ) : totalCandidates === 0 && totalMonitoring === 0 ? (
                        <div className="figma-card text-center py-10">
                            <div className="text-gray-400 text-sm">No grievance clusters have reached the threshold yet.</div>
                            <div className="text-xs text-gray-300 mt-2">Clusters appear here when 100+ complaints accumulate for the same issue + location.</div>
                        </div>
                    ) : (
                        <>
                            {/* CSR-Ready (200+) */}
                            {totalCandidates > 0 && (
                                <div>
                                    <div className="text-xs font-bold uppercase text-gray-500 tracking-wide mb-3">
                                        🔴 CSR-Ready — 200+ Verified Complaints
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {proposals.candidates.map((c, i) => (
                                            <div key={i} className="figma-card border-l-4" style={{ borderLeftColor: '#c62828' }}>
                                                <div className="flex justify-between items-start">
                                                    <div>
                                                        <div className="font-semibold text-gray-900">{c.category}</div>
                                                        <div className="text-sm text-gray-500 mt-0.5">{c.area}</div>
                                                    </div>
                                                    <span className="sansad-badge" style={{ background: '#fbe9e7', color: '#c62828' }}>
                                                        {c.volume} complaints
                                                    </span>
                                                </div>
                                                <div className="mt-3 flex items-center gap-3">
                                                    <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                                                        <div className="h-full rounded-full" style={{
                                                            width: `${Math.min(100, c.progress_pct)}%`,
                                                            background: '#c62828'
                                                        }} />
                                                    </div>
                                                    <span className="text-xs font-mono text-gray-500">{c.progress_pct}%</span>
                                                </div>
                                                <div className="mt-2 text-xs text-gray-400">
                                                    CSR Sector: <span className="font-semibold text-gray-600">{c.csr_sector}</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Monitoring (100-199) */}
                            {totalMonitoring > 0 && (
                                <div className="mt-6">
                                    <div className="text-xs font-bold uppercase text-gray-500 tracking-wide mb-3">
                                        🟡 Monitoring — Approaching Threshold
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {proposals.monitoring.map((c, i) => (
                                            <div key={i} className="figma-card border-l-4" style={{ borderLeftColor: '#f57f17' }}>
                                                <div className="flex justify-between items-start">
                                                    <div>
                                                        <div className="font-semibold text-gray-900">{c.category}</div>
                                                        <div className="text-sm text-gray-500 mt-0.5">{c.area}</div>
                                                    </div>
                                                    <span className="sansad-badge" style={{ background: '#fff8e1', color: '#f57f17' }}>
                                                        {c.volume} complaints
                                                    </span>
                                                </div>
                                                <div className="mt-3 flex items-center gap-3">
                                                    <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                                                        <div className="h-full rounded-full" style={{
                                                            width: `${Math.min(100, c.progress_pct)}%`,
                                                            background: '#f57f17'
                                                        }} />
                                                    </div>
                                                    <span className="text-xs font-mono text-gray-500">{c.progress_pct}%</span>
                                                </div>
                                                <div className="mt-2 text-xs text-gray-400">
                                                    CSR Sector: <span className="font-semibold text-gray-600">{c.csr_sector}</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}

            {/* ═══════════════════════════════════════════
                TAB 2: Strategic Matches (Live Gaps ↔ Companies)
               ═══════════════════════════════════════════ */}
            {activeTab === 'matches' && (
                <div className="space-y-4 animate-fade-in">
                    {matchesLoading ? (
                        <div className="text-center py-10 text-gray-400 text-sm">Matching live grievances to CSR companies...</div>
                    ) : strategicMatches.length === 0 ? (
                        <div className="figma-card text-center py-10">
                            <div className="text-gray-400 text-sm">No strategic matches found yet.</div>
                            <div className="text-xs text-gray-300 mt-2">Matches appear when grievance clusters (100+ complaints) can be mapped to CSR-eligible companies.</div>
                        </div>
                    ) : (
                        strategicMatches.map((match, mi) => {
                            const bc = badgeColor(match.badge);
                            return (
                                <div key={mi} className="figma-card">
                                    <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="font-bold text-gray-900 text-base">{match.category}</span>
                                                <span className="sansad-badge" style={{ background: bc.bg, color: bc.text }}>
                                                    {match.badge}
                                                </span>
                                            </div>
                                            <div className="text-sm text-gray-500 mt-0.5">
                                                {match.area} · <span className="font-semibold">{match.volume}</span> verified complaints
                                            </div>
                                        </div>
                                        <div className="text-xs text-gray-400">
                                            Matched sectors: {match.matched_sectors?.join(', ')}
                                        </div>
                                    </div>

                                    {match.matched_companies?.length > 0 ? (
                                        <div className="overflow-x-auto">
                                            <table className="sansad-table w-full">
                                                <thead>
                                                    <tr>
                                                        <th>Company</th>
                                                        <th>Sector</th>
                                                        <th>3Y Spend</th>
                                                        <th>District</th>
                                                        <th>Action</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {match.matched_companies.map((comp, ci) => {
                                                        const dprKey = `${match.category}-${comp.Company}`;
                                                        return (
                                                            <tr key={ci}>
                                                                <td className="font-semibold text-gray-900">{comp.Company}</td>
                                                                <td className="text-gray-600">{comp.Sector || 'N/A'}</td>
                                                                <td className="font-mono text-xs text-gray-800">{comp.Total_3Y || 'N/A'}</td>
                                                                <td className="text-gray-600">{comp.District || '—'}</td>
                                                                <td>
                                                                    <div className="relative">
                                                                        <button
                                                                            onClick={() => generateDPR(match, comp)}
                                                                            disabled={dprLoading === dprKey}
                                                                            className="figma-btn-outline whitespace-nowrap"
                                                                            style={{ color, borderColor: color }}>
                                                                            {dprLoading === dprKey ? 'Generating...' : 'Generate DPR'}
                                                                        </button>
                                                                        {dprContent[dprKey] && (
                                                                            <div className="absolute right-0 top-full mt-2 w-96 bg-white border border-gray-200 shadow-xl rounded-xl z-50 p-4 animate-fade-in">
                                                                                <div className="text-xs font-semibold text-gray-900 mb-2">
                                                                                    DPR: {match.category} × {comp.Company}
                                                                                </div>
                                                                                <pre className="text-xs text-gray-600 bg-gray-50 p-3 rounded-lg border border-gray-100 max-h-48 overflow-y-auto whitespace-pre-wrap font-serif mb-3">
                                                                                    {dprContent[dprKey]}
                                                                                </pre>
                                                                                <div className="flex justify-end gap-2">
                                                                                    <button onClick={() => setDprContent(prev => { const n = { ...prev }; delete n[dprKey]; return n; })}
                                                                                        className="px-3 py-1.5 text-xs text-gray-500">Close</button>
                                                                                    <button onClick={() => downloadText(dprContent[dprKey], `DPR_${match.category}_${comp.Company}.txt`)}
                                                                                        className="px-3 py-1.5 text-xs font-bold text-white rounded-md" style={{ background: color }}>
                                                                                        Download DPR
                                                                                    </button>
                                                                                </div>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                </td>
                                                            </tr>
                                                        );
                                                    })}
                                                </tbody>
                                            </table>
                                        </div>
                                    ) : (
                                        <div className="text-xs text-gray-400 italic">No matching companies found in the database for this sector.</div>
                                    )}
                                </div>
                            );
                        })
                    )}
                </div>
            )}

            {/* ═══════════════════════════════════════════
                TAB 3: Company Database (existing static data)
               ═══════════════════════════════════════════ */}
            {activeTab === 'database' && (
                <div className="space-y-4 animate-fade-in">
                    {/* Search Bar */}
                    <div className="figma-search-wrap">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-gray-400 shrink-0">
                            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
                        </svg>
                        <input type="text" className="figma-search" placeholder="Search by company or focus area..."
                            value={search} onChange={e => setSearch(e.target.value)} />
                    </div>

                    {/* Pill Filters */}
                    <div className="flex flex-wrap gap-2">
                        {CSR_PILLS.map(p => (
                            <button key={p} onClick={() => setSelectedSector(p)}
                                className={`pill-filter ${selectedSector === p ? 'pill-filter-active' : ''}`}
                                style={selectedSector === p ? { background: color, borderColor: color, color: '#fff' } : {}}>
                                {p}
                            </button>
                        ))}
                    </div>

                    {/* Company Table */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                        <div className="overflow-x-auto">
                            {companiesLoading ? (
                                <div className="text-center py-10 text-gray-400 text-sm">Loading companies...</div>
                            ) : companies.length === 0 ? (
                                <div className="text-center py-14 text-gray-400 text-sm">No companies found matching criteria.</div>
                            ) : (
                                <table className="sansad-table w-full">
                                    <thead>
                                        <tr>
                                            <th className="pl-6">#</th>
                                            <th>COMPANY</th>
                                            <th>SECTOR</th>
                                            <th>FOCUS AREA</th>
                                            <th>BUDGET</th>
                                            <th>PROJECT TYPE</th>
                                            <th>ACTION</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {companies.map((c, i) => (
                                            <tr key={i}>
                                                <td className="pl-6 text-gray-500 font-mono text-xs">{i + 1}</td>
                                                <td className="font-semibold text-gray-900">{c.Company}</td>
                                                <td className="text-gray-600">{c.Sector || 'N/A'}</td>
                                                <td className="text-gray-600 max-w-[150px] truncate" title={c.Gap_Analysis || 'Community Development'}>
                                                    {c.Gap_Analysis || 'Community Development'}
                                                </td>
                                                <td className="font-mono text-xs text-gray-800">{c.Total_3Y || 'Undisclosed'}</td>
                                                <td>
                                                    <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-gray-100 text-gray-600">
                                                        {c.Company_Type || 'Funding'}
                                                    </span>
                                                </td>
                                                <td>
                                                    <div className="relative">
                                                        <button onClick={() => draftLetter(c)}
                                                            disabled={draftLoading === c.Company}
                                                            className="figma-btn-outline whitespace-nowrap"
                                                            style={{ color, borderColor: color }}>
                                                            {draftLoading === c.Company ? 'Drafting...' : 'Generate Draft'}
                                                        </button>
                                                        {draftContent[c.Company] && (
                                                            <div className="absolute right-0 top-full mt-2 w-80 bg-white border border-gray-200 shadow-xl rounded-xl z-50 p-4 animate-fade-in">
                                                                <div className="text-xs font-semibold text-gray-900 mb-2">Draft Letter ready</div>
                                                                <pre className="text-xs text-gray-600 bg-gray-50 p-3 rounded-lg border border-gray-100 max-h-40 overflow-y-auto whitespace-pre-wrap font-serif mb-3">
                                                                    {draftContent[c.Company]}
                                                                </pre>
                                                                <div className="flex justify-end gap-2">
                                                                    <button onClick={() => setDraftContent(prev => { const n = { ...prev }; delete n[c.Company]; return n; })}
                                                                        className="px-3 py-1.5 text-xs text-gray-500">Close</button>
                                                                    <button onClick={() => downloadText(draftContent[c.Company], `CSR_Proposal_${c.Company}.txt`)}
                                                                        className="px-3 py-1.5 text-xs font-bold text-white rounded-md" style={{ background: color }}>
                                                                        Download
                                                                    </button>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
