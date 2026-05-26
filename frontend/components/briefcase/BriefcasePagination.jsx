'use client';

import { briefcaseFonts, briefcasePalette as P } from '@/components/briefcase/briefcase-shared';

const { mono: MONO } = briefcaseFonts;

export default function BriefcasePagination({ page, totalPages, totalCases, shown, onPrevious, onNext }) {
    return (
        <div
            className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
            style={{
                padding: '10px 22px',
                borderTop: `1px solid ${P.hair}`,
                background: P.surfaceWarm,
            }}
        >
            <span style={{ fontFamily: MONO, fontSize: 10, color: P.ink3, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                Showing {shown} of {totalCases.toLocaleString()} · live updates pinned to top
            </span>
            <div style={{ display: 'flex', gap: 4 }}>
                <button onClick={onPrevious} disabled={page <= 1} style={pageButton(page <= 1)}>‹</button>
                <button style={pageButton(false, true)}>{page}</button>
                <button onClick={onNext} disabled={page >= totalPages} style={pageButton(page >= totalPages)}>›</button>
            </div>
        </div>
    );
}

function pageButton(disabled, active = false) {
    return {
        minWidth: 26,
        height: 26,
        padding: '0 6px',
        background: active ? P.ink : 'transparent',
        color: active ? P.paper : P.ink2,
        border: `1px solid ${P.hair}`,
        fontSize: 11,
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: 'inherit',
        opacity: disabled ? 0.45 : 1,
    };
}
