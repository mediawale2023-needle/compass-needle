'use client';

import DashboardDonut from '@/components/dashboard/DashboardDonut';
import DashboardSectionFrame from '@/components/dashboard/DashboardSectionFrame';
import { dashboardFonts, dashboardPalette as P } from '@/lib/dashboard-theme';

const { mono: MONO } = dashboardFonts;

export default function DashboardWorkloadCard({ summary }) {
    const categories = summary?.category_breakdown || {};
    const colors = [P.green, P.saffron, P.blue, P.greenDeep, '#A14B12', P.ink2];
    const entries = Object.entries(categories).sort((a, b) => b[1] - a[1]).slice(0, 6);
    const total = entries.reduce((sum, [, value]) => sum + value, 0) || 1;
    const segments = entries.map(([label, value], index) => ({ label, v: value, color: colors[index % colors.length] }));
    const totalLabel = total > 999 ? `${(total / 1000).toFixed(1)}K` : String(total);

    return (
        <DashboardSectionFrame title="Workload by category" meta={`${total} cases`} contentPadding={16}>
            {segments.length > 0 ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, flex: 1 }}>
                    <DashboardDonut segments={segments} size={96} thickness={16} label={totalLabel} sub="total" />
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 5 }}>
                        {segments.map((segment) => {
                            const percentage = ((segment.v / total) * 100).toFixed(0);
                            return (
                                <div key={segment.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5 }}>
                                    <span style={{ width: 8, height: 8, background: segment.color, flexShrink: 0 }} />
                                    <span style={{ flex: 1, color: P.ink, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{segment.label}</span>
                                    <span style={{ fontFamily: MONO, color: P.ink2, fontSize: 10.5 }}>{segment.v}</span>
                                    <span style={{ fontFamily: MONO, color: P.ink3, width: 28, textAlign: 'right', fontSize: 10.5 }}>{percentage}%</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            ) : (
                <div style={{ minHeight: 152, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <span style={{ color: P.ink3, fontSize: 12 }}>No data yet</span>
                </div>
            )}
        </DashboardSectionFrame>
    );
}
