'use client';

import { Skeleton } from '@/components/ui/skeleton';
import { briefcaseFonts, briefcasePalette as P, BriefcaseIcon, BriefcaseStatusPill } from '@/components/briefcase/briefcase-shared';

const { serif: SERIF, mono: MONO } = briefcaseFonts;

export default function BriefcaseClustersView({ clusters, loading, onSelectCase }) {
    if (loading) {
        return <div className="space-y-3 py-6">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-24 w-full rounded-none" />)}</div>;
    }

    if (clusters.length === 0) {
        return <div style={{ textAlign: 'center', padding: '64px 0', color: P.ink3 }}>No clusters found in the last 30 days.</div>;
    }

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 14, padding: '18px 22px 22px' }}>
            {clusters.map((cluster, index) => (
                <article key={index} style={{ border: `1px solid ${P.hair}`, background: P.surface }}>
                    <div style={{ padding: '14px 16px', borderBottom: `1px solid ${P.hair}`, background: P.surfaceWarm }}>
                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
                            <div>
                                <div style={{ fontFamily: MONO, fontSize: 9.5, color: P.ink3, letterSpacing: '0.14em', textTransform: 'uppercase' }}>
                                    Cluster {String(index + 1).padStart(2, '0')}
                                </div>
                                <div style={{ fontFamily: SERIF, fontSize: 22, lineHeight: 1.05, color: P.ink, marginTop: 4 }}>
                                    {cluster.category || 'Emerging issue'}
                                </div>
                                {cluster.location && cluster.location !== 'Unknown' && (
                                    <div style={{ fontSize: 11.5, color: P.ink2, marginTop: 4 }}>{cluster.location}</div>
                                )}
                            </div>
                            <div
                                style={{
                                    minWidth: 42,
                                    padding: '6px 8px',
                                    background: P.greenDeep,
                                    color: P.paper,
                                    fontFamily: MONO,
                                    fontSize: 10,
                                    textAlign: 'center',
                                }}
                            >
                                {cluster.count} cases
                            </div>
                        </div>
                    </div>
                    <div style={{ padding: '10px 14px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {(cluster.cases || []).slice(0, 5).map((item) => (
                            <div
                                key={item.id}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 8,
                                    cursor: 'pointer',
                                    padding: '7px 8px',
                                    background: P.paper,
                                    border: `1px solid ${P.hair}`,
                                }}
                                onClick={() => onSelectCase({ id: item.id, ...item })}
                            >
                                <BriefcaseStatusPill status={item.status} />
                                <div style={{ minWidth: 0, flex: 1 }}>
                                    <div style={{ fontFamily: MONO, fontSize: 10, color: P.ink3 }}>#{item.id}</div>
                                    <div
                                        style={{
                                            fontSize: 11.5,
                                            color: P.ink2,
                                            lineHeight: 1.3,
                                            whiteSpace: 'nowrap',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                        }}
                                    >
                                        {item.message_preview}
                                    </div>
                                </div>
                                <BriefcaseIcon name="chevr" size={12} color={P.ink3} />
                            </div>
                        ))}
                        {cluster.count > 5 && (
                            <p style={{ fontSize: 10.5, color: P.ink3 }}>+{cluster.count - 5} more cases in this cluster</p>
                        )}
                    </div>
                </article>
            ))}
        </div>
    );
}
