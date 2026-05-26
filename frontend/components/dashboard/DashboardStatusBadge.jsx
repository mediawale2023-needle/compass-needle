'use client';

import { getDashboardStatusLabel, getDashboardStatusStyle } from '@/lib/dashboard-theme';

export default function DashboardStatusBadge({ status }) {
    const style = getDashboardStatusStyle(status);

    return (
        <span
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                padding: '1px 7px',
                background: style.bg,
                color: style.fg,
                fontSize: 10,
                fontWeight: 600,
            }}
        >
            <span style={{ width: 4, height: 4, background: style.dot, borderRadius: '50%' }} />
            {getDashboardStatusLabel(status)}
        </span>
    );
}
