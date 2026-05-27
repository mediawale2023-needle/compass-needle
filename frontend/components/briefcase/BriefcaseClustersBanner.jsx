'use client';

import { briefcaseFonts, briefcasePalette as P, BriefcaseIcon } from '@/components/briefcase/briefcase-shared';

const { serif: SERIF, mono: MONO } = briefcaseFonts;

export default function BriefcaseClustersBanner({ clusters = [], onOpenClusters }) {
    if (!clusters.length) {
        return null;
    }

    const promoted = clusters.slice(0, 3);

    return (
        <section
            className="flex flex-col gap-4 md:flex-row md:items-center md:gap-4"
            style={{
                border: `1px solid ${P.hair}`,
                background: `linear-gradient(135deg, ${P.surfaceWarm} 0%, ${P.paper} 100%)`,
                padding: '16px 18px',
            }}
        >
            <div style={{ minWidth: 0, flex: 1 }}>
                <div
                    style={{
                        fontFamily: MONO,
                        fontSize: 9.5,
                        letterSpacing: '0.16em',
                        textTransform: 'uppercase',
                        color: P.ink3,
                        marginBottom: 6,
                    }}
                >
                    Promoted clusters
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                    {promoted.map((cluster, index) => (
                        <div
                            key={`${cluster.category}-${cluster.location || index}`}
                            style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 8,
                                padding: '8px 10px',
                                border: `1px solid ${P.hair}`,
                                background: P.surface,
                                minWidth: 0,
                            }}
                        >
                            <span
                                style={{
                                    width: 22,
                                    height: 22,
                                    background: P.greenDeep,
                                    color: P.paper,
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    fontFamily: MONO,
                                    fontSize: 10,
                                    fontWeight: 700,
                                }}
                            >
                                {cluster.count}
                            </span>
                            <div style={{ minWidth: 0 }}>
                                <div
                                    style={{
                                        fontSize: 12.5,
                                        color: P.ink,
                                        fontWeight: 600,
                                        lineHeight: 1.15,
                                        whiteSpace: 'nowrap',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                    }}
                                >
                                    {cluster.category || 'Emerging issue'}
                                </div>
                                <div style={{ fontSize: 10.5, color: P.ink3, marginTop: 2 }}>
                                    {cluster.location && cluster.location !== 'Unknown' ? cluster.location : 'Constituency wide'}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
            <div className="w-full text-left md:w-auto md:text-right">
                <div style={{ fontFamily: SERIF, fontSize: 20, color: P.ink, lineHeight: 1.1 }}>
                    Similar grievances are surfacing in waves.
                </div>
                <button
                    onClick={onOpenClusters}
                    style={{
                        marginTop: 10,
                        border: 'none',
                        background: P.greenDeep,
                        color: P.paper,
                        padding: '8px 12px',
                        fontSize: 11.5,
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        fontFamily: 'inherit',
                    }}
                >
                    <BriefcaseIcon name="cluster" size={12} color={P.paper} />
                    Review clusters
                </button>
            </div>
        </section>
    );
}
