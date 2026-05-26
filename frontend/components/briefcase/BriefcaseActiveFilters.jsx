'use client';

import { briefcaseFonts, briefcasePalette as P, BriefcaseIcon, TABS } from '@/components/briefcase/briefcase-shared';

const { mono: MONO } = briefcaseFonts;

export default function BriefcaseActiveFilters({
    assemblyFilter,
    casesCount,
    categoryFilter,
    color,
    loading,
    locationFilter,
    onClearAssembly,
    onClearCategory,
    onClearLocation,
    onResetStatus,
    statusFilter,
}) {
    if ((!categoryFilter && !locationFilter && !assemblyFilter && statusFilter === 'needs') || statusFilter === 'clusters' || statusFilter === 'deleted') {
        return null;
    }

    const chipStyle = {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '5px 8px',
        border: `1px solid ${P.hair}`,
        background: P.surface,
        color: P.ink2,
        fontSize: 11,
    };

    return (
        <div
            style={{
                padding: '10px 22px',
                borderBottom: `1px solid ${P.hair}`,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                flexWrap: 'wrap',
                background: P.surfaceWarm,
            }}
        >
            <span
                style={{
                    fontFamily: MONO,
                    fontSize: 9.5,
                    color: P.ink3,
                    letterSpacing: '0.14em',
                    textTransform: 'uppercase',
                }}
            >
                Active filters
            </span>
            {statusFilter !== 'needs' && (
                <span style={chipStyle}>
                    Status: {TABS.find((tab) => tab.key === statusFilter)?.label || statusFilter}
                    <button onClick={onResetStatus} style={dismissStyle}>
                        <BriefcaseIcon name="x" size={10} color={P.ink2} />
                    </button>
                </span>
            )}
            {categoryFilter && (
                <span style={{ ...chipStyle, background: color, borderColor: color, color: '#fff' }}>
                    Category: {categoryFilter}
                    <button onClick={onClearCategory} style={dismissStyle}>
                        <BriefcaseIcon name="x" size={10} color="#fff" />
                    </button>
                </span>
            )}
            {locationFilter && (
                <span style={{ ...chipStyle, background: color, borderColor: color, color: '#fff' }}>
                    Location: {locationFilter}
                    <button onClick={onClearLocation} style={dismissStyle}>
                        <BriefcaseIcon name="x" size={10} color="#fff" />
                    </button>
                </span>
            )}
            {assemblyFilter && (
                <span style={{ ...chipStyle, background: color, borderColor: color, color: '#fff' }}>
                    Constituency: {assemblyFilter}
                    <button onClick={onClearAssembly} style={dismissStyle}>
                        <BriefcaseIcon name="x" size={10} color="#fff" />
                    </button>
                </span>
            )}
            <span style={{ fontSize: 11, color: P.ink3, marginLeft: 4 }}>
                {loading ? '...' : `${casesCount} case${casesCount !== 1 ? 's' : ''}`}
            </span>
        </div>
    );
}

const dismissStyle = {
    border: 'none',
    background: 'transparent',
    padding: 0,
    marginLeft: 2,
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
};
