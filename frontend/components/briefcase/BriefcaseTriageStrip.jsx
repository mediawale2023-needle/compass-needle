'use client';

import { briefcaseFonts, briefcasePalette as P, BriefcaseIcon } from '@/components/briefcase/briefcase-shared';

const { serif: SERIF, mono: MONO } = briefcaseFonts;

function StatCard({ accent, icon, label, value, note }) {
    return (
        <div
            style={{
                background: P.surface,
                border: `1px solid ${P.hair}`,
                padding: '16px 18px',
                minHeight: 108,
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
                boxShadow: '0 1px 0 rgba(19,52,43,0.03)',
            }}
        >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                <span
                    style={{
                        fontFamily: MONO,
                        fontSize: 9.5,
                        letterSpacing: '0.16em',
                        textTransform: 'uppercase',
                        color: P.ink3,
                    }}
                >
                    {label}
                </span>
                <span
                    style={{
                        width: 26,
                        height: 26,
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: accent,
                        color: accent === P.saffron ? P.greenDeep : P.paper,
                    }}
                >
                    <BriefcaseIcon
                        name={icon}
                        size={14}
                        color={accent === P.saffron ? P.greenDeep : P.paper}
                        stroke={2}
                    />
                </span>
            </div>
            <div style={{ fontFamily: SERIF, fontSize: 30, lineHeight: 0.95, color: P.ink }}>{value.toLocaleString()}</div>
            <div style={{ fontSize: 12, lineHeight: 1.35, color: P.ink2 }}>{note}</div>
        </div>
    );
}

export default function BriefcaseTriageStrip({ triage }) {
    const stats = [
        {
            label: 'Needs you',
            value: triage?.needsYou || 0,
            note: 'Open cases requiring MP office intervention or review.',
            accent: P.saffron,
            icon: 'briefcase',
        },
        {
            label: 'New today',
            value: triage?.newToday || 0,
            note: 'Fresh grievances received since the start of today.',
            accent: P.green,
            icon: 'bell',
        },
        {
            label: 'Uncategorised',
            value: triage?.uncategorised || 0,
            note: 'Cases still waiting for final issue classification.',
            accent: '#B45309',
            icon: 'filter',
        },
        {
            label: 'SLA risk',
            value: triage?.slaRisk || 0,
            note: 'Cases nearing or breaching the 24 hour response threshold.',
            accent: P.red,
            icon: 'eye',
        },
    ];

    return (
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {stats.map((stat) => (
                <StatCard key={stat.label} {...stat} />
            ))}
        </section>
    );
}
