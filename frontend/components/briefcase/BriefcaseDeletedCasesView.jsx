'use client';

import { Skeleton } from '@/components/ui/skeleton';
import { briefcaseFonts, briefcasePalette as P } from '@/components/briefcase/briefcase-shared';

const { mono: MONO } = briefcaseFonts;

export default function BriefcaseDeletedCasesView({ deletedCases, loading, onRestore }) {
    if (loading) {
        return <div className="space-y-3 py-6">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full rounded-none" />)}</div>;
    }

    if (deletedCases.length === 0) {
        return <div style={{ textAlign: 'center', padding: '64px 0', color: P.ink3 }}>No deleted cases in the last 7 days.</div>;
    }

    return (
        <div>
            <div className="md:hidden" style={{ padding: '10px 12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                {deletedCases.map((item) => (
                    <article key={item.id} style={{ border: `1px solid ${P.hair}`, background: P.paper, padding: 12 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                            <div style={{ fontFamily: MONO, fontSize: 10.5, color: P.ink3 }}>#{item.id}</div>
                            <button
                                onClick={() => onRestore(item.id)}
                                style={{
                                    border: `1px solid ${P.hairStrong}`,
                                    background: P.surface,
                                    color: P.ink,
                                    padding: '6px 10px',
                                    fontSize: 11.5,
                                    cursor: 'pointer',
                                }}
                            >
                                Restore
                            </button>
                        </div>
                        <div style={{ fontSize: 12.5, color: P.ink, fontWeight: 600, marginTop: 6 }}>{item.category || 'General'}</div>
                        <div style={{ fontFamily: MONO, fontSize: 10.5, color: P.ink2, marginTop: 4 }}>{item.user_phone || '-'}</div>
                        <div style={{ fontSize: 11, color: P.ink3, marginTop: 8 }}>
                            Deleted at: {item.deleted_at ? new Date(item.deleted_at).toLocaleString('en-IN') : '-'}
                        </div>
                        <div style={{ fontSize: 11, color: P.ink3, marginTop: 2 }}>
                            Deleted by: {item.deleted_by || '-'}
                        </div>
                    </article>
                ))}
            </div>

            <div className="hidden md:block" style={{ padding: '0 22px 22px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr style={{ background: P.surfaceWarm }}>
                            {['Ref', 'Contact', 'Category', 'Deleted at', 'Deleted by', 'Action'].map((heading) => (
                                <th
                                    key={heading}
                                    style={{
                                        textAlign: heading === 'Action' ? 'right' : 'left',
                                        padding: '10px 12px',
                                        fontFamily: MONO,
                                        fontSize: 9.5,
                                        letterSpacing: '0.14em',
                                        color: P.ink3,
                                        textTransform: 'uppercase',
                                        borderBottom: `1px solid ${P.hair}`,
                                    }}
                                >
                                    {heading}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {deletedCases.map((item) => (
                            <tr key={item.id} style={{ borderBottom: `1px solid ${P.hair}` }}>
                                <td style={{ padding: '12px', fontFamily: MONO, fontSize: 11, color: P.ink3 }}>#{item.id}</td>
                                <td style={{ padding: '12px', fontFamily: MONO, fontSize: 11, color: P.ink2 }}>{item.user_phone || '-'}</td>
                                <td style={{ padding: '12px', fontSize: 12.5, color: P.ink }}>{item.category || 'General'}</td>
                                <td style={{ padding: '12px', fontSize: 11.5, color: P.ink2 }}>
                                    {item.deleted_at ? new Date(item.deleted_at).toLocaleString('en-IN') : '-'}
                                </td>
                                <td style={{ padding: '12px', fontSize: 11.5, color: P.ink2 }}>{item.deleted_by || '-'}</td>
                                <td style={{ padding: '12px', textAlign: 'right' }}>
                                    <button
                                        onClick={() => onRestore(item.id)}
                                        style={{
                                            border: `1px solid ${P.hairStrong}`,
                                            background: P.surface,
                                            color: P.ink,
                                            padding: '6px 10px',
                                            fontSize: 11.5,
                                            cursor: 'pointer',
                                            fontFamily: 'inherit',
                                        }}
                                    >
                                        Restore
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
