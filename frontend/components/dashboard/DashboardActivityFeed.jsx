'use client';

import { useState } from 'react';
import { dashboardFonts, dashboardPalette as P } from '@/lib/dashboard-theme';

const { serif: SERIF, mono: MONO, sans: SANS } = dashboardFonts;

const INITIAL_LIMIT = 5;

function formatTimeAgo(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    const minutes = Math.floor((Date.now() - date) / 60000);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
}

export default function DashboardActivityFeed({ cases, letters }) {
    const [expanded, setExpanded] = useState(false);

    const all = [
        ...cases.slice(0, 6).map((caseItem) => ({
            time: caseItem.updated_at || caseItem.created_at,
            who: caseItem.assigned_to || 'System',
            action: (caseItem.status || 'new').toLowerCase() === 'resolved' ? 'resolved' : 'updated',
            object: `Case #${caseItem.id} · ${caseItem.category || 'Grievance'}`,
            tag: 'grievance',
        })),
        ...letters.slice(0, 4).map((letter) => ({
            time: letter.updated_at || letter.created_at,
            who: letter.created_by || 'Staff',
            action: letter.status === 'sent' ? 'sent' : 'drafted',
            object: letter.subject || `Letter #${letter.id}`,
            tag: 'letter',
        })),
    ].sort((a, b) => new Date(b.time) - new Date(a.time));

    const visible = expanded ? all : all.slice(0, INITIAL_LIMIT);
    const hasMore = all.length > INITIAL_LIMIT;
    const tagColor = { grievance: P.saffron, letter: P.blue, press: P.red, engagement: P.green };

    return (
        <section className="min-w-0" style={{ background: P.surface, border: `1px solid ${P.hair}`, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', padding: '12px 14px 10px' }}>
                <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 15, color: P.ink }}>Activity · recent</div>
                <span style={{ fontFamily: MONO, fontSize: 9.5, color: P.green, letterSpacing: '0.1em', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                    <span style={{ width: 6, height: 6, background: P.green, borderRadius: '50%' }} />
                    LIVE
                </span>
            </div>
            <div style={{ flex: 1, minHeight: 0, padding: '0 14px' }}>
                {all.length === 0 ? (
                    <div style={{ color: P.ink3, fontSize: 12, textAlign: 'center', paddingTop: 12 }}>
                        No recent activity
                    </div>
                ) : (
                    visible.map((item, index) => (
                        <div
                            key={`${item.tag}-${item.object}-${index}`}
                            style={{
                                display: 'grid',
                                gridTemplateColumns: '48px 8px 1fr',
                                gap: 8,
                                padding: '6px 0',
                                borderBottom: index < visible.length - 1 ? `1px solid ${P.hair}` : 'none',
                                alignItems: 'flex-start',
                            }}
                        >
                            <div style={{ fontFamily: MONO, fontSize: 10, color: P.ink3, paddingTop: 2 }}>
                                {formatTimeAgo(item.time)}
                            </div>
                            <div style={{ width: 6, height: 6, background: tagColor[item.tag] || P.ink2, marginTop: 6, borderRadius: '50%' }} />
                            <div style={{ fontSize: 11.5, color: P.ink, lineHeight: 1.4 }}>
                                <span style={{ fontWeight: 600 }}>{item.who}</span>
                                <span style={{ color: P.ink2 }}> {item.action} </span>
                                <span>{item.object}</span>
                            </div>
                        </div>
                    ))
                )}
            </div>
            {hasMore && (
                <button
                    type="button"
                    onClick={() => setExpanded(!expanded)}
                    style={{
                        width: '100%',
                        padding: '7px 14px',
                        background: P.surfaceWarm,
                        color: P.ink2,
                        fontSize: 10.5,
                        fontFamily: MONO,
                        fontWeight: 600,
                        letterSpacing: '0.06em',
                        cursor: 'pointer',
                        border: 'none',
                        borderTop: `1px solid ${P.hair}`,
                        textAlign: 'center',
                    }}
                >
                    {expanded ? `VIEW LESS ↑` : `VIEW ${all.length - INITIAL_LIMIT} MORE ↓`}
                </button>
            )}
        </section>
    );
}
