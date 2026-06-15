'use client';

import { useState } from 'react';
import Link from 'next/link';
import DashboardStatusBadge from '@/components/dashboard/DashboardStatusBadge';
import { dashboardFonts, dashboardPalette as P } from '@/lib/dashboard-theme';

const { serif: SERIF, mono: MONO, sans: SANS } = dashboardFonts;

function formatAge(createdAt) {
    if (!createdAt) return '—';
    const days = Math.floor((Date.now() - new Date(createdAt)) / 86400000);
    return days === 0 ? 'today' : `${days}d`;
}

export default function DashboardGrievanceQueue({ cases, onCaseClick }) {
    const [filter, setFilter] = useState('All');
    const tabs = ['All', 'Open', 'Needs Review', 'In Progress', 'Resolved'];

    const filtered = cases
        .filter((caseItem) => {
            if (filter === 'All') return true;
            const status = (caseItem.status || '').toLowerCase();
            if (filter === 'Open') return status === 'new';
            if (filter === 'Needs Review') return status === 'pending_review';
            if (filter === 'In Progress') return status === 'in_progress';
            if (filter === 'Resolved') return status === 'resolved';
            return true;
        })
        .slice(0, 10);

    return (
        <section className="min-w-0" style={{ background: P.surface, border: `1px solid ${P.hair}`, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div
                className="flex-wrap"
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 14,
                    padding: '12px 16px',
                    borderBottom: `1px solid ${P.hair}`,
                }}
            >
                <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 15, color: P.ink }}>Grievance queue</div>
                <span style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.12em', color: P.ink3, textTransform: 'uppercase' }}>
                    auto-prioritised by SLA + age
                </span>
                <div style={{ flex: 1 }} />
                <div style={{ display: 'flex', border: `1px solid ${P.hair}`, flexWrap: 'wrap', width: '100%', maxWidth: '100%' }}>
                    {tabs.map((tab, index) => (
                        <button
                            key={tab}
                            onClick={() => setFilter(tab)}
                            style={{
                                padding: '4px 10px',
                                border: 'none',
                                background: filter === tab ? P.ink : 'transparent',
                                color: filter === tab ? P.paper : P.ink2,
                                fontSize: 10.5,
                                fontWeight: 600,
                                letterSpacing: '0.04em',
                                cursor: 'pointer',
                                fontFamily: SANS,
                                borderRight: index < tabs.length - 1 ? `1px solid ${P.hair}` : 'none',
                                flex: '1 1 auto',
                            }}
                        >
                            {tab}
                        </button>
                    ))}
                </div>
            </div>

            <div style={{ overflow: 'auto', flex: 1, minHeight: 0 }}>
                <table style={{ width: '100%', minWidth: 640, borderCollapse: 'collapse', tableLayout: 'fixed' }}>
                    <colgroup>
                        <col style={{ width: 28 }} />
                        <col style={{ width: 78 }} />
                        <col />
                        <col style={{ width: 90 }} />
                        <col style={{ width: 46 }} />
                        <col style={{ width: 100 }} />
                    </colgroup>
                    <thead>
                        <tr style={{ background: P.surfaceWarm }}>
                            {['#', 'Cat', 'Subject', 'Phone / ID', 'Age', 'Status'].map((heading, index) => (
                                <th
                                    key={heading}
                                    style={{
                                        textAlign: 'left',
                                        padding: '7px 10px',
                                        fontFamily: MONO,
                                        fontSize: 9,
                                        letterSpacing: '0.14em',
                                        color: P.ink3,
                                        textTransform: 'uppercase',
                                        fontWeight: 500,
                                        borderBottom: `1px solid ${P.hair}`,
                                        borderRight: index === 1 ? `1px solid ${P.hair}` : 'none',
                                    }}
                                >
                                    {heading}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.length === 0 ? (
                            <tr>
                                <td colSpan={6} style={{ padding: '24px 16px', textAlign: 'center', color: P.ink3, fontSize: 12 }}>
                                    No cases found
                                </td>
                            </tr>
                        ) : (
                            filtered.map((caseItem, index) => (
                                <tr
                                    key={caseItem.id}
                                    style={{
                                        borderBottom: `1px solid ${P.hair}`,
                                        background: index % 2 === 1 ? 'rgba(0,0,0,0.012)' : 'transparent',
                                        cursor: 'pointer',
                                    }}
                                    onClick={() => onCaseClick(caseItem.id)}
                                >
                                    <td style={{ padding: '7px 10px', fontFamily: MONO, fontSize: 10, color: P.ink3 }}>
                                        {(index + 1).toString().padStart(2, '0')}
                                    </td>
                                    <td
                                        style={{
                                            padding: '7px 12px 7px 10px',
                                            fontSize: 11.5,
                                            color: P.ink2,
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            whiteSpace: 'nowrap',
                                            borderRight: `1px solid ${P.hair}`,
                                        }}
                                    >
                                        {caseItem.category || '—'}
                                    </td>
                                    <td style={{ padding: '7px 10px 7px 14px', fontSize: 11.5, color: P.ink, lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {caseItem.raw_message
                                            ? caseItem.raw_message.slice(0, 80) + (caseItem.raw_message.length > 80 ? '…' : '')
                                            : caseItem.category || '—'}
                                    </td>
                                    <td style={{ padding: '7px 10px', fontFamily: MONO, fontSize: 10.5, color: P.ink2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {caseItem.user_phone || caseItem.user_id || '—'}
                                    </td>
                                    <td style={{ padding: '7px 10px', fontFamily: MONO, fontSize: 10.5, color: P.ink2 }}>
                                        {formatAge(caseItem.created_at)}
                                    </td>
                                    <td style={{ padding: '7px 10px' }}>
                                        <DashboardStatusBadge status={caseItem.status} />
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            <div
                className="flex-wrap gap-2"
                style={{
                    padding: '8px 16px',
                    borderTop: `1px solid ${P.hair}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    background: P.surfaceWarm,
                }}
            >
                <span style={{ fontFamily: MONO, fontSize: 10, color: P.ink3, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                    Showing {filtered.length} case{filtered.length !== 1 ? 's' : ''}
                </span>
                <Link
                    href="/dashboard/sansadx"
                    style={{
                        padding: '4px 10px',
                        background: 'transparent',
                        border: `1px solid ${P.hair}`,
                        fontSize: 10.5,
                        color: P.ink2,
                        fontFamily: SANS,
                        textDecoration: 'none',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                    }}
                >
                    Open full queue →
                </Link>
            </div>
        </section>
    );
}
