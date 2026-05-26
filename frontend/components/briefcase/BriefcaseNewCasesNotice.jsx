'use client';

import { briefcasePalette as P } from '@/components/briefcase/briefcase-shared';

export default function BriefcaseNewCasesNotice({ onRefresh }) {
    return (
        <div
            style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
                padding: '10px 14px',
                border: `1px solid ${P.green}`,
                background: P.greenTint,
                color: P.greenDeep,
                fontSize: 12,
                fontWeight: 600,
            }}
        >
            <span>New cases arrived since last refresh.</span>
            <button
                onClick={onRefresh}
                style={{
                    fontSize: 10.5,
                    textTransform: 'uppercase',
                    letterSpacing: '0.12em',
                    border: 'none',
                    background: 'transparent',
                    color: P.greenDeep,
                    cursor: 'pointer',
                }}
            >
                Refresh now
            </button>
        </div>
    );
}
