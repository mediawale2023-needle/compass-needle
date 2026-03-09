'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, AI_TIMEOUT } from '@/lib/api';

const CSR_PILLS = ['All', 'Steel & Mining', 'Information Technology', 'Banking & Finance', 'Healthcare', 'Energy', 'Automobile'];

export default function CSRPage() {
    const { user } = useAuth();
    const [companies, setCompanies] = useState([]);
    const [search, setSearch] = useState('');
    const [selectedSector, setSelectedSector] = useState('All');
    const [loading, setLoading] = useState(true);
    const [draftContent, setDraftContent] = useState({});
    const [draftLoading, setDraftLoading] = useState(null);
    const color = user?.theme_color || '#006a4d';

    const fetchCompanies = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (search) params.set('search', search);
            if (selectedSector !== 'All') params.set('sector', selectedSector);

            const data = await apiGet(`/api/csr/companies?${params}`);
            setCompanies(data.companies || []);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    useEffect(() => { fetchCompanies(); }, [search, selectedSector]);

    const draftLetter = async (company) => {
        setDraftLoading(company.Company);
        try {
            const data = await apiPost('/api/csr/draft-letter', {
                company: company.Company,
                sector: company.Sector || '',
                spend_history: company.Spend_History || company.History || {},
                letter_type: 'upscale',
            }, { timeout: AI_TIMEOUT, noRetry: true });
            setDraftContent(prev => ({ ...prev, [company.Company]: data.content }));
        } catch (err) {
            setDraftContent(prev => ({ ...prev, [company.Company]: 'Error generating draft.' }));
        } finally {
            setDraftLoading(null);
        }
    };

    const downloadText = (text, filename) => {
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="space-y-6">
            <h1 className="text-lg font-bold text-gray-900">CSR Intelligence</h1>

            {/* Search Bar matching Figma */}
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

            {/* Main Table Card */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                <div className="overflow-x-auto">
                    {loading ? (
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
    );
}
