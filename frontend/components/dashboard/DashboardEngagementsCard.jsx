'use client';

import { dashboardFonts, dashboardPalette as P } from '@/lib/dashboard-theme';

const { serif: SERIF, mono: MONO } = dashboardFonts;

export default function DashboardEngagementsCard() {
    const today = new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' });
    const items = [
        { time: '09:00', dur: '60m', title: 'Constituency workspace hours', loc: 'Constituency Workspace', tag: 'Public' },
        { time: '11:30', dur: '30m', title: 'Team review · Grievance pipeline', loc: 'War room', tag: 'Internal' },
        { time: '14:00', dur: '90m', title: 'Site visit — Ward inspection', loc: 'Field', tag: 'Field' },
        { time: '16:30', dur: '45m', title: 'Press briefing', loc: 'Press cabin', tag: 'Media' },
    ];
    const tagColor = { Public: P.green, Internal: P.ink2, Field: P.saffron, Media: P.red, Govt: P.blue };

    return (
        <section style={{ background: P.surface, border: `1px solid ${P.hair}`, padding: 14, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
                <div>
                    <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 15, color: P.ink }}>Today · Schedule</div>
                    <div style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.12em', color: P.ink3, marginTop: 2, textTransform: 'uppercase' }}>{today}</div>
                </div>
            </div>

            <div style={{ flex: 1, overflow: 'hidden' }}>
                {items.map((item, index) => (
                    <div
                        key={`${item.time}-${item.title}`}
                        style={{
                            display: 'grid',
                            gridTemplateColumns: '46px 1fr auto',
                            gap: 12,
                            padding: '7px 0',
                            borderBottom: index < items.length - 1 ? `1px solid ${P.hair}` : 'none',
                            alignItems: 'center',
                        }}
                    >
                        <div style={{ fontFamily: MONO, fontSize: 11, color: P.ink2, fontWeight: 600 }}>{item.time}</div>
                        <div>
                            <div style={{ fontSize: 11.5, color: P.ink, fontWeight: 500, lineHeight: 1.3 }}>{item.title}</div>
                            <div style={{ fontSize: 10, color: P.ink3, marginTop: 1 }}>{item.loc} · {item.dur}</div>
                        </div>
                        <span style={{ fontFamily: MONO, fontSize: 9, letterSpacing: '0.1em', color: tagColor[item.tag] || P.ink2, textTransform: 'uppercase', fontWeight: 700 }}>
                            {item.tag}
                        </span>
                    </div>
                ))}
            </div>
        </section>
    );
}
