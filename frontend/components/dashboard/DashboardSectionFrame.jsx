'use client';

import { dashboardFonts, dashboardPalette } from '@/lib/dashboard-theme';

export default function DashboardSectionFrame({
    title,
    meta,
    action,
    children,
    headerPadding = 16,
    contentPadding = 0,
    bodyStyle = {},
    style = {},
}) {
    return (
        <section
            style={{
                background: dashboardPalette.surface,
                border: `1px solid ${dashboardPalette.hair}`,
                display: 'flex',
                flexDirection: 'column',
                ...style,
            }}
        >
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: `12px ${headerPadding}px`,
                    borderBottom: `1px solid ${dashboardPalette.hair}`,
                }}
            >
                <div style={{ fontFamily: dashboardFonts.serif, fontWeight: 600, fontSize: 15, color: dashboardPalette.ink }}>
                    {title}
                </div>
                {meta ? (
                    <span
                        style={{
                            fontFamily: dashboardFonts.mono,
                            fontSize: 9.5,
                            color: dashboardPalette.ink3,
                            letterSpacing: '0.12em',
                            textTransform: 'uppercase',
                        }}
                    >
                        {meta}
                    </span>
                ) : null}
                <div style={{ flex: 1 }} />
                {action}
            </div>
            <div style={{ padding: contentPadding, ...bodyStyle }}>
                {children}
            </div>
        </section>
    );
}
