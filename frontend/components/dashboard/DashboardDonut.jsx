'use client';

import { dashboardFonts, dashboardPalette } from '@/lib/dashboard-theme';

export default function DashboardDonut({
    segments,
    size = 96,
    thickness = 16,
    label,
    sub,
}) {
    const total = segments.reduce((sum, segment) => sum + segment.v, 0) || 1;
    const radius = (size - thickness) / 2;
    const circumference = 2 * Math.PI * radius;
    let offsetAccumulator = 0;

    return (
        <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
            <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={dashboardPalette.paperDeep}
                    strokeWidth={thickness}
                />
                {segments.map((segment, index) => {
                    const segmentLength = (segment.v / total) * circumference;
                    const dashOffset = circumference - offsetAccumulator;
                    offsetAccumulator += segmentLength;
                    return (
                        <circle
                            key={index}
                            cx={size / 2}
                            cy={size / 2}
                            r={radius}
                            fill="none"
                            stroke={segment.color}
                            strokeWidth={thickness}
                            strokeDasharray={`${segmentLength} ${circumference - segmentLength}`}
                            strokeDashoffset={dashOffset}
                        />
                    );
                })}
            </svg>
            <div
                style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    textAlign: 'center',
                }}
            >
                <div style={{ fontFamily: dashboardFonts.serif, fontWeight: 600, fontSize: 18, color: dashboardPalette.ink, lineHeight: 1 }}>
                    {label}
                </div>
                <div
                    style={{
                        fontSize: 9,
                        color: dashboardPalette.ink3,
                        letterSpacing: '0.1em',
                        textTransform: 'uppercase',
                        marginTop: 2,
                        fontFamily: dashboardFonts.mono,
                    }}
                >
                    {sub}
                </div>
            </div>
        </div>
    );
}
