'use client';

import Link from 'next/link';
import DashboardMiniBars from '@/components/dashboard/DashboardMiniBars';
import { dashboardFonts, dashboardPalette as P } from '@/lib/dashboard-theme';

const { serif: SERIF, mono: MONO } = dashboardFonts;

function synthesizeSeries(base, points = 10) {
    const seed = Math.max(1, Number(base) || 1);
    return Array.from(
        { length: points },
        (_, index) => {
            const offset = ((seed * (index + 3)) % 7) - 3;
            return Math.max(1, seed - (points - index) * 3 + offset);
        }
    );
}

export default function DashboardKpiTiles({ summary }) {
    const statuses = summary?.status_breakdown || {};
    const total = Object.values(statuses).reduce((a, b) => a + b, 0);
    const resolved = statuses.resolved || 0;
    const sla = total > 0 ? ((resolved / total) * 100).toFixed(1) : '—';

    const tiles = [
        {
            label: 'Grievances open',
            value: (statuses.new || 0) + (statuses.in_progress || 0),
            detail: `+${statuses.new || 0} new`,
            color: P.saffron,
            data: synthesizeSeries((statuses.new || 0) + (statuses.in_progress || 0)),
            href: '/dashboard/sansadx?status=new',
        },
        {
            label: 'SLA compliance',
            value: sla === '—' ? '—' : `${sla}%`,
            detail: `${resolved} resolved`,
            color: P.green,
            data: synthesizeSeries(resolved),
            href: '/dashboard/sansadx?status=resolved',
        },
        {
            label: 'Total cases',
            value: total,
            detail: `${statuses.in_progress || 0} in progress`,
            color: P.blue,
            data: synthesizeSeries(total),
            href: '/dashboard/sansadx',
        },
        {
            label: 'Critical / escalated',
            value: statuses.escalated || (summary?.critical_count ?? 0),
            detail: `${(summary?.red_zones || []).length} red zones`,
            color: P.red,
            data: synthesizeSeries(statuses.escalated || 0),
            href: '/dashboard/sansadx?status=escalated',
        },
    ];

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3.5 md:gap-[14px]">
            {tiles.map((tile) => (
                <Link key={tile.label} href={tile.href} style={{ textDecoration: 'none' }}>
                    <div
                        style={{
                            background: P.surface,
                            border: `1px solid ${P.hair}`,
                            padding: '14px 14px 12px',
                            display: 'flex',
                            flexDirection: 'column',
                            cursor: 'pointer',
                            transition: 'opacity 0.15s',
                        }}
                        onMouseOver={(event) => {
                            event.currentTarget.style.opacity = '0.85';
                        }}
                        onMouseOut={(event) => {
                            event.currentTarget.style.opacity = '1';
                        }}
                    >
                        <div style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.14em', color: P.ink3, textTransform: 'uppercase' }}>
                            {tile.label}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginTop: 6, gap: 12 }}>
                            <div>
                                <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 30, color: P.ink, letterSpacing: '-0.01em', lineHeight: 1 }}>
                                    {tile.value}
                                </div>
                            </div>
                            <DashboardMiniBars data={tile.data} width={88} height={36} color={tile.color} />
                        </div>
                        <div
                            style={{
                                fontSize: 11,
                                color: P.ink2,
                                marginTop: 8,
                                paddingTop: 8,
                                borderTop: `1px solid ${P.hair}`,
                            }}
                        >
                            {tile.detail}
                        </div>
                    </div>
                </Link>
            ))}
        </div>
    );
}
