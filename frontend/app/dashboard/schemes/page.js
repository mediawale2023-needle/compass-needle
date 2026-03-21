'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';

export default function ParliamentScrutinyPage() {
    const { user } = useAuth();
    const [fundIntel, setFundIntel] = useState(null);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('all');
    const [expanded, setExpanded] = useState(null);

    const color = user?.theme_color || '#006a4d';

    useEffect(() => {
        apiGet('/api/schemes/fund-intel')
            .then(fi => { if (fi && fi.ministries) setFundIntel(fi); })
            .catch(() => {})
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div className="text-center py-20 text-gray-500 text-sm">Loading...</div>;

    if (!fundIntel) return (
        <div className="text-center py-20 text-gray-400 text-sm">
            No parliament scrutiny data available.
        </div>
    );

    const meta = fundIntel.metadata || {};
    const ministries = fundIntel.ministries || [];

    const filtered = ministries.filter(m => {
        if (filter === 'scrutinized') return m.total_questions > 0;
        if (filter === 'unspent') return (m.tag_counts?.unspent || 0) > 0;
        if (filter === 'utilization') return (m.tag_counts?.utilization || 0) > 0;
        return true;
    });

    const totalQs = meta.total_fund_questions || ministries.reduce((s, m) => s + m.total_questions, 0);
    const scrutinizedCount = ministries.filter(m => m.total_questions > 0).length;
    const unspentFlags = ministries.reduce((s, m) => s + (m.tag_counts?.unspent || 0), 0);

    const severityColor = s => s >= 50 ? '#dc2626' : s >= 25 ? '#f59e0b' : '#6b7280';
    const tagColor = tag => ({ utilization: '#3b82f6', unspent: '#dc2626', allocation: '#8b5cf6', release: '#06b6d4', delay: '#f59e0b' })[tag] || '#6b7280';
    const tagLabel = tag => ({ utilization: 'Utilization', unspent: 'Unspent', allocation: 'Allocation', release: 'Release', budget: 'Budget', delay: 'Delay', general: 'General' })[tag] || tag;

    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-bold text-gray-800">Parliament Scrutiny</h1>
                <span className="text-xs text-gray-400">435 Q&As from ePARLib · LS {meta.lok_sabha || 18} · FY {meta.financial_year || '2025-26'}</span>
            </div>

            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-4">
                {[
                    { label: 'Parliament Questions', value: totalQs, sub: 'on fund utilisation' },
                    { label: 'Ministries Questioned', value: scrutinizedCount, sub: `of ${ministries.length} tracked` },
                    { label: 'Unspent Fund Flags', value: unspentFlags, sub: 'Q&As about unused funds' },
                ].map(s => (
                    <div key={s.label} className="sansad-card">
                        <div className="sansad-card-body text-center py-3">
                            <div className="text-xl font-bold" style={{ color }}>{s.value}</div>
                            <div className="text-[10px] text-gray-500 uppercase">{s.label}</div>
                            <div className="text-[9px] text-gray-400">{s.sub}</div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Filter pills */}
            <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-400 font-semibold uppercase">Filter:</span>
                {[
                    { key: 'all', label: 'All Ministries' },
                    { key: 'scrutinized', label: 'Parliament Questioned' },
                    { key: 'unspent', label: 'Unspent Fund Flags' },
                    { key: 'utilization', label: 'Utilization Q&As' },
                ].map(f => (
                    <button key={f.key} onClick={() => setFilter(f.key)}
                        className="px-3 py-1 text-[11px] font-semibold border"
                        style={filter === f.key
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
                    const isOpen = expanded === i;
                    const hasPQ = m.total_questions > 0;
                    const maxBudget = ministries[0]?.budget_cr || 1;
                    const budgetPct = Math.max(2, ((m.budget_cr || 0) / maxBudget) * 100);
                    const unspentCount = m.tag_counts?.unspent || 0;
                    const severity = m.severity_score || 0;

                    return (
                        <div key={i} className="sansad-card" style={{
                            borderLeft: hasPQ ? `4px solid ${severityColor(severity)}` : '4px solid transparent'
                        }}>
                            <div className="sansad-card-body py-3">
                                <div className="flex items-center justify-between cursor-pointer"
                                    onClick={() => setExpanded(isOpen ? null : i)}>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <span className="text-sm font-semibold text-gray-800 truncate">
                                                {m.ministry.replace('Ministry of ', '').replace('Ministry for ', '')}
                                            </span>
                                            {hasPQ && (
                                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0" style={{
                                                    background: severityColor(severity) + '18',
                                                    color: severityColor(severity)
                                                }}>
                                                    {m.total_questions} Parliament Q{m.total_questions > 1 ? 's' : ''}
                                                </span>
                                            )}
                                            {unspentCount > 0 && (
                                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0"
                                                    style={{ background: '#fef2f2', color: '#dc2626' }}>
                                                    {unspentCount} Unspent Flag{unspentCount > 1 ? 's' : ''}
                                                </span>
                                            )}
                                        </div>
                                        {m.budget_cr > 0 && (
                                            <div className="mt-1.5 flex items-center gap-2">
                                                <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                                    <div className="h-full rounded-full" style={{ width: `${budgetPct}%`, background: color, opacity: 0.65 }} />
                                                </div>
                                                <span className="text-[11px] font-bold shrink-0" style={{ color }}>
                                                    ₹{m.budget_cr.toLocaleString('en-IN')} Cr
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                    <span className="text-gray-300 ml-4 text-xs">{isOpen ? '▲' : '▼'}</span>
                                </div>

                                {isOpen && (
                                    <div className="mt-3 pt-3 border-t space-y-4" style={{ borderColor: '#eee' }}>
                                        <div className="grid grid-cols-3 gap-3">
                                            <div className="text-center py-2 bg-gray-50 border" style={{ borderColor: '#eee' }}>
                                                <div className="text-sm font-bold text-gray-800">{m.total_questions}</div>
                                                <div className="text-[10px] text-gray-500 uppercase">Parliament Q&As</div>
                                                <div className="text-[9px] text-gray-400">LS {meta.lok_sabha || 18}</div>
                                            </div>
                                            <div className="text-center py-2 bg-gray-50 border" style={{ borderColor: '#eee' }}>
                                                <div className="text-sm font-bold" style={{ color: unspentCount > 0 ? '#dc2626' : '#6b7280' }}>
                                                    {unspentCount > 0 ? `${unspentCount} raised` : '—'}
                                                </div>
                                                <div className="text-[10px] text-gray-500 uppercase">Unspent / Lapsed</div>
                                                <div className="text-[9px] text-gray-400">questions about unused funds</div>
                                            </div>
                                            <div className="text-center py-2 bg-gray-50 border" style={{ borderColor: '#eee' }}>
                                                <div className="text-sm font-bold" style={{ color: severityColor(severity) }}>
                                                    {severity > 0 ? severity : '—'}
                                                </div>
                                                <div className="text-[10px] text-gray-500 uppercase">Scrutiny Score</div>
                                                <div className="text-[9px] text-gray-400">based on question volume</div>
                                            </div>
                                        </div>

                                        {hasPQ && m.tag_counts && Object.keys(m.tag_counts).length > 0 && (
                                            <div>
                                                <div className="text-[10px] text-gray-500 uppercase font-semibold mb-1.5">What MPs Asked About</div>
                                                <div className="flex gap-2 flex-wrap">
                                                    {Object.entries(m.tag_counts)
                                                        .sort((a, b) => b[1] - a[1])
                                                        .map(([tag, cnt]) => (
                                                            <span key={tag} className="text-[11px] font-semibold px-2 py-0.5 rounded" style={{
                                                                background: tagColor(tag) + '18', color: tagColor(tag)
                                                            }}>
                                                                {tagLabel(tag)}: {cnt}
                                                            </span>
                                                        ))}
                                                </div>
                                            </div>
                                        )}

                                        {m.schemes?.length > 0 && (
                                            <div>
                                                <div className="text-[10px] text-gray-500 uppercase font-semibold mb-1.5">Schemes Under Question</div>
                                                <div className="space-y-1">
                                                    {m.schemes.slice(0, 8).map((s, j) => (
                                                        <div key={j} className="flex items-center justify-between text-xs py-1 border-b last:border-0" style={{ borderColor: '#f0f0f0' }}>
                                                            <span className="text-gray-700 font-medium truncate" style={{ maxWidth: '65%' }}>{s.name}</span>
                                                            <span className="font-semibold text-gray-600 shrink-0">
                                                                {s.alloc_cr > 0 ? `₹${s.alloc_cr.toLocaleString('en-IN')} Cr` : 'N/A'}
                                                            </span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {(m.questions || []).length > 0 && (
                                            <div>
                                                <div className="text-[10px] text-gray-500 uppercase font-semibold mb-1.5">Parliament Questions Raised</div>
                                                <div className="space-y-1.5">
                                                    {[...(m.questions || [])].sort((a, b) => (b.date || '').localeCompare(a.date || '')).slice(0, 8).map((q, j) => (
                                                        <div key={j} className="text-xs py-1.5 border-b last:border-0" style={{ borderColor: '#f0f0f0' }}>
                                                            <div className="flex items-start gap-2">
                                                                <span className="text-gray-400 shrink-0 font-mono text-[10px] mt-0.5">{q.date?.slice(0, 7) || '—'}</span>
                                                                <span className="text-gray-700">{q.title}</span>
                                                            </div>
                                                            {q.tags?.filter(t => t !== 'general').length > 0 && (
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
                                                    {(m.questions || []).length > 8 && (
                                                        <div className="text-[10px] text-gray-400 text-right">
                                                            +{m.questions.length - 8} more questions
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

            {/* myscheme.gov.in referral */}
            <div className="sansad-card border-l-4" style={{ borderLeftColor: color }}>
                <div className="sansad-card-body py-4 flex items-center justify-between gap-4">
                    <div>
                        <div className="text-sm font-semibold text-gray-800">Looking up scheme eligibility for a constituent?</div>
                        <div className="text-xs text-gray-500 mt-0.5">
                            Use myscheme.gov.in — the government's official portal with verified eligibility criteria for 300+ schemes.
                        </div>
                    </div>
                    <a href="https://www.myscheme.gov.in" target="_blank" rel="noopener noreferrer"
                        className="shrink-0 px-4 py-2 text-sm font-semibold text-white rounded"
                        style={{ background: color }}>
                        Open myscheme.gov.in ↗
                    </a>
                </div>
            </div>

            <div className="text-[10px] text-gray-400 text-right">
                Source: Parliament Q&A data from ePARLib (sansad.in) · LS {meta.lok_sabha || 18} · FY {meta.financial_year || '2025-26'} · Updated: {meta.enriched_at || meta.scraped_at || 'N/A'}
            </div>
        </div>
    );
}
