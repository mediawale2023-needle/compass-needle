'use client';

import Link from 'next/link';
import DashboardSectionFrame from '@/components/dashboard/DashboardSectionFrame';
import { dashboardFonts, dashboardPalette as P } from '@/lib/dashboard-theme';

const { mono: MONO, sans: SANS } = dashboardFonts;

function getLetterStatusStyle(status) {
    const norm = (status || '').toLowerCase();
    if (norm === 'new') return { fg: P.saffron, bg: P.saffronTint };
    if (norm === 'sent') return { fg: P.greenInk, bg: P.greenTint };
    if (norm === 'draft') return { fg: P.ink2, bg: P.neutralTint };
    if (norm === 'signed') return { fg: P.greenInk, bg: P.greenTint };
    if (norm === 'pending') return { fg: P.saffron, bg: P.saffronTint };
    return { fg: P.ink2, bg: P.neutralTint };
}

export default function DashboardLettersCard({ letters }) {
    return (
        <DashboardSectionFrame
            title="Letters & drafts"
            meta={`${letters.length} in pipeline`}
            action={(
                <Link
                    href="/dashboard/drafter"
                    style={{
                        padding: '4px 9px',
                        background: P.green,
                        color: '#F5EFE0',
                        border: 'none',
                        fontSize: 10,
                        letterSpacing: '0.08em',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        fontFamily: SANS,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        textDecoration: 'none',
                    }}
                >
                    + Draft
                </Link>
            )}
            bodyStyle={{ flex: 1, overflow: 'auto', minHeight: 0 }}
        >
            {letters.length === 0 ? (
                <div style={{ padding: '24px 16px', textAlign: 'center', color: P.ink3, fontSize: 12 }}>
                    No letters in pipeline
                </div>
            ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <tbody>
                        {letters.slice(0, 6).map((letter, index) => {
                            const status = getLetterStatusStyle(letter.status);
                            return (
                                <tr key={letter.id || index} style={{ borderBottom: index < letters.length - 1 ? `1px solid ${P.hair}` : 'none' }}>
                                    <td style={{ padding: '8px 12px 8px 16px', fontFamily: MONO, fontSize: 10, color: P.ink2, verticalAlign: 'top', whiteSpace: 'nowrap' }}>
                                        #{(letter.id || index + 1).toString().padStart(4, '0')}
                                    </td>
                                    <td style={{ padding: '8px 10px', verticalAlign: 'top' }}>
                                        <div style={{ fontSize: 11.5, color: P.ink, fontWeight: 500, lineHeight: 1.3 }}>
                                            {letter.subject || letter.content_preview || letter.title || '—'}
                                        </div>
                                        <div style={{ fontSize: 10, color: P.ink3, marginTop: 2, fontStyle: 'italic' }}>
                                            {letter.addressee || letter.recipient || letter.direction || '—'}
                                        </div>
                                    </td>
                                    <td style={{ padding: '8px 16px 8px 10px', textAlign: 'right', verticalAlign: 'top', whiteSpace: 'nowrap' }}>
                                        <span
                                            style={{
                                                padding: '1px 6px',
                                                background: status.bg,
                                                color: status.fg,
                                                fontSize: 9.5,
                                                fontWeight: 700,
                                                letterSpacing: '0.04em',
                                                textTransform: 'uppercase',
                                            }}
                                        >
                                            {letter.status || 'Draft'}
                                        </span>
                                        <div style={{ fontFamily: MONO, fontSize: 9.5, color: P.ink3, marginTop: 3 }}>
                                            {letter.created_at ? new Date(letter.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '—'}
                                        </div>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            )}
        </DashboardSectionFrame>
    );
}
