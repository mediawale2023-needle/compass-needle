'use client';

import DashboardSectionFrame from '@/components/dashboard/DashboardSectionFrame';
import { dashboardFonts, dashboardPalette as P } from '@/lib/dashboard-theme';

const { serif: SERIF, mono: MONO } = dashboardFonts;

function getToneStyle(tone) {
    if (!tone) return { fg: P.ink2, bg: P.neutralTint };
    const norm = tone.toLowerCase();
    if (norm === 'positive') return { fg: P.greenInk, bg: P.greenTint };
    if (norm === 'negative') return { fg: P.red, bg: P.redTint };
    return { fg: P.ink2, bg: P.neutralTint };
}

export default function DashboardPressCard({ news }) {
    return (
        <DashboardSectionFrame title="Press monitoring" meta={`${news.length} articles`} bodyStyle={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {news.length === 0 ? (
                <div style={{ padding: '24px 16px', textAlign: 'center', color: P.ink3, fontSize: 12 }}>
                    No coverage fetched yet
                </div>
            ) : (
                news.slice(0, 6).map((item, index) => {
                    const tone = getToneStyle(item.sentiment || item.tone);
                    return (
                        <div
                            key={`${item.link || item.title}-${index}`}
                            style={{
                                display: 'grid',
                                gridTemplateColumns: '12px 1fr',
                                gap: 10,
                                padding: '8px 16px',
                                borderBottom: index < Math.min(news.length, 6) - 1 ? `1px solid ${P.hair}` : 'none',
                                alignItems: 'flex-start',
                            }}
                        >
                            <div style={{ width: 4, height: 32, background: tone.fg, marginTop: 2, flexShrink: 0 }} />
                            <div>
                                <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', marginBottom: 2 }}>
                                    <div style={{ fontSize: 11.5, fontWeight: 600, color: P.ink, fontFamily: SERIF }}>
                                        {item.source || 'Unknown'}
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
