'use client';

import { dashboardPalette } from '@/lib/dashboard-theme';

export default function DashboardMiniBars({
    data,
    width = 88,
    height = 36,
    color = dashboardPalette.green,
}) {
    if (!data?.length) return <div style={{ width, height }} />;

    const max = Math.max(...data, 1);
    const count = data.length;
    const barWidth = Math.max(2, (width - (count - 1) * 2) / count);

    return (
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: 'block', flexShrink: 0 }}>
            {data.map((value, index) => {
                const barHeight = Math.max(2, (value / max) * height);
                const x = index * (barWidth + 2);
                const y = height - barHeight;
                return (
                    <rect
                        key={index}
                        x={x}
                        y={y}
                        width={barWidth}
                        height={barHeight}
                        fill={color}
                        opacity={index === count - 1 ? 1 : 0.55}
                    />
                );
            })}
        </svg>
    );
}
