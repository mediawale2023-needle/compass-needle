'use client';

import { useMemo, useState } from 'react';
import DashboardSectionFrame from '@/components/dashboard/DashboardSectionFrame';
import { dashboardFonts, dashboardPalette as P } from '@/lib/dashboard-theme';

const { serif: SERIF, mono: MONO } = dashboardFonts;

function getToneStyle(tone) {
    if (!tone) return { fg: P.ink2, bg: P.neutralTint };
    const norm = tone.toLowerCase();
    if (norm === 'positive' || norm === 'pos') return { fg: P.greenInk, bg: P.greenTint };
    if (norm === 'negative' || norm === 'neg') return { fg: P.red, bg: P.redTint };
    return { fg: P.ink2, bg: P.neutralTint };
}

function tabButtonStyle(active) {
    return {
        border: `1px solid ${active ? P.green : P.hair}`,
        background: active ? P.greenTint : P.surface,
        color: active ? P.greenInk : P.ink2,
        padding: '7px 10px',
        fontFamily: MONO,
        fontSize: 10,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        cursor: 'pointer',
    };
}

export default function DashboardPressCard({ news }) {
    const [newsTab, setNewsTab] = useState('national');
    const [search, setSearch] = useState('');
    const [source, setSource] = useState('');
    const feeds = news && typeof news === 'object' ? news : { national: [], local: [] };
    const activeNews = feeds[newsTab] || [];
    const allCount = (feeds.national?.length || 0) + (feeds.local?.length || 0);

    const sources = useMemo(
        () => [...new Set(activeNews.map((item) => item.source).filter(Boolean))].sort(),
        [activeNews],
    );

    const filteredNews = useMemo(() => {
        const term = search.trim().toLowerCase();
        return activeNews.filter((item) => {
            const haystack = [item.title, item.source].filter(Boolean).join(' ').toLowerCase();
            const matchesSearch = !term || haystack.includes(term);
            const matchesSource = !source || item.source === source;
            return matchesSearch && matchesSource;
        });
    }, [activeNews, search, source]);

    return (
        <DashboardSectionFrame
            title="Media Centre"
            meta={`${allCount} articles`}
            bodyStyle={{ flex: 1, overflow: 'auto', minHeight: 0, paddingTop: 0 }}
        >
            <div style={{ padding: '0 16px 10px', borderBottom: `1px solid ${P.hair}` }}>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
                    <button type="button" onClick={() => { setNewsTab('national'); setSource(''); }} style={tabButtonStyle(newsTab === 'national')}>
                        National
                    </button>
                    <button type="button" onClick={() => { setNewsTab('local'); setSource(''); }} style={tabButtonStyle(newsTab === 'local')}>
                        Local
                    </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_120px] gap-2">
                    <input
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                        placeholder={`Search ${newsTab} coverage...`}
                        style={{
                            border: `1px solid ${P.hair}`,
                            background: P.surface,
                            color: P.ink,
                            padding: '8px 10px',
                            fontSize: 11,
                            outline: 'none',
                        }}
                    />
                    <select
                        value={source}
                        onChange={(event) => setSource(event.target.value)}
                        style={{
                            border: `1px solid ${P.hair}`,
                            background: P.surface,
                            color: P.ink,
                            padding: '8px 10px',
                            fontSize: 11,
                            outline: 'none',
                        }}
                    >
                        <option value="">All sources</option>
                        {sources.map((itemSource) => (
                            <option key={itemSource} value={itemSource}>{itemSource}</option>
                        ))}
                    </select>
                </div>
            </div>

            {filteredNews.length === 0 ? (
                <div style={{ padding: '24px 16px', textAlign: 'center', color: P.ink3, fontSize: 12 }}>
                    {newsTab === 'local' ? 'No local or digital media coverage fetched yet' : 'No national coverage fetched yet'}
                </div>
            ) : (
                filteredNews.slice(0, 8).map((item, index) => {
                    const tone = getToneStyle(item.sentiment || item.tone);
                    return (
                        <div
                            key={`${item.link || item.title}-${index}`}
                            style={{
                                display: 'grid',
                                gridTemplateColumns: '12px 1fr',
                                gap: 10,
                                padding: '10px 16px',
                                borderBottom: index < Math.min(filteredNews.length, 8) - 1 ? `1px solid ${P.hair}` : 'none',
                                alignItems: 'flex-start',
                            }}
                        >
                            <div style={{ width: 4, height: 34, background: tone.fg, marginTop: 2, flexShrink: 0 }} />
                            <div>
                                <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap', marginBottom: 3 }}>
                                    <div style={{ fontSize: 11.5, fontWeight: 600, color: P.ink, fontFamily: SERIF }}>
                                        {item.source || 'Unknown'}
                                    </div>
                                    <div
                                        style={{
                                            fontFamily: MONO,
                                            fontSize: 9.5,
                                            color: tone.fg,
                                            background: tone.bg,
                                            padding: '2px 6px',
                                        }}
                                    >
                                        {newsTab === 'local' ? 'LOCAL' : 'NATIONAL'}
                                    </div>
                                    <div style={{ fontFamily: MONO, fontSize: 9.5, color: P.ink3 }}>
                                        {item.published ? new Date(item.published).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''}
                                    </div>
                                </div>
                                <a
                                    href={item.link || item.url || '#'}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{ fontSize: 11, color: P.ink, lineHeight: 1.35, textDecoration: 'none' }}
                                >
                                    {item.title}
                                </a>
                            </div>
                        </div>
                    );
                })
            )}
        </DashboardSectionFrame>
    );
}
