'use client';

import { Skeleton } from '@/components/ui/skeleton';
import { briefcaseFonts, briefcasePalette as P } from '@/components/briefcase/briefcase-shared';

import { gen2Type as T } from '@/lib/briefcase-tokens';

const { mono: MONO } = briefcaseFonts;

export default function BriefcaseDeletedCasesView({ deletedCases, loading, onRestore }) {
    if (loading) {
        return <div className="space-y-3 py-6">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full rounded-none" />)}</div>;
    }

    if (deletedCases.length === 0) {
        return <div style={{ textAlign: 'center', padding: '64px 0', color: P.ink3, fontSize: T.body }}>No deleted cases in the last 7 days.</div>;
    }

    return (
        <div style={{ padding: '0 22px 22px', overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: 640, borderCollapse: 'collapse' }}>
                <thead>
                    <tr style={{ background: P.surfaceWarm }}>
                        {['Ref', 'Contact', 'Category', 'Deleted at', 'Deleted by', 'Action'].map((heading) => (
                            <th
                                key={heading}
                                style={{
                                    textAlign: heading === 'Action' ? 'right' : 'left',
                                    padding: '10px 12px',
                                    fontFamily: MONO,
                                    fontSize: T.label,
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
                            <td style={{ padding: '12px', fontFamily: MONO, fontSize: T.meta, color: P.ink3 }}>#{item.id}</td>
                            <td style={{ padding: '12px', fontFamily: MONO, fontSize: T.meta, color: P.ink2 }}>{item.user_phone || '-'}</td>
                            <td style={{ padding: '12px', fontSize: T.title, color: P.ink }}>{item.category || 'General'}</td>
                            <td style={{ padding: '12px', fontSize: T.small, color: P.ink2 }}>
                                {item.deleted_at ? new Date(item.deleted_at).toLocaleString('en-IN') : '-'}
                            </td>
                            <td style={{ padding: '12px', fontSize: T.small, color: P.ink2 }}>{item.deleted_by || '-'}</td>
                            <td style={{ padding: '12px', textAlign: 'right' }}>
                                <button
                                    onClick={() => onRestore(item.id)}
                                    style={{
                                        border: `1px solid ${P.hairStrong}`,
                                        background: P.surface,
                                        color: P.ink,
                                        padding: '6px 10px',
                                        fontSize: T.control,
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
    );
}
