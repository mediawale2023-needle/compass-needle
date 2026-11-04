'use client';

import { briefcasePalette as P } from '@/components/briefcase/briefcase-shared';
import { gen2Type as T } from '@/lib/briefcase-tokens';

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
                fontSize: T.small,
                fontWeight: 600,
            }}
        >
            <span>New cases arrived since last refresh.</span>
            <button
                onClick={onRefresh}
                style={{
                    fontSize: T.label,
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
