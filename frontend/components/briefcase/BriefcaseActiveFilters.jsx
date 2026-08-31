'use client';

// Renders ONLY when a real advanced filter (category / location / assembly) is
// active. The status tab is already shown as an active tab and is not echoed
// here. Count reflects the filtered total, not the current page size.
const C = {
    surface: '#FFFEFB',
    surfaceWarm: '#F8F1E0',
    border: '#E4DECB',
    borderStrong: '#C9BFA9',
    ink: '#211F19',
    muted: '#6C6858',
    faint: '#8A8270',
    greenDeep: '#245F45',
};
const MONO = '"IBM Plex Mono", ui-monospace, SFMono-Regular, monospace';

export default function BriefcaseActiveFilters({
    assemblyFilter,
    categoryFilter,
    locationFilter,
    loading,
    totalCases,
    onClearAssembly,
    onClearCategory,
    onClearLocation,
    onClearAll,
    statusFilter,
}) {
    const activeChips = [];
    if (categoryFilter) activeChips.push({ label: `Category: ${categoryFilter}`, onClear: onClearCategory });
    if (locationFilter) activeChips.push({ label: `Location: ${locationFilter}`, onClear: onClearLocation });
    if (assemblyFilter) activeChips.push({ label: `Constituency: ${assemblyFilter}`, onClear: onClearAssembly });

    if (activeChips.length === 0 || statusFilter === 'clusters' || statusFilter === 'deleted') {
        return null;
    }

    return (
        <div
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                flexWrap: 'wrap',
                padding: '8px 22px',
                borderBottom: `1px solid ${C.border}`,
                background: C.surface,
            }}
        >
            <span style={{ fontFamily: MONO, fontSize: 9, letterSpacing: '0.14em', textTransform: 'uppercase', color: C.faint }}>
                Active
            </span>
            {activeChips.map((chip) => (
                <span
                    key={chip.label}
                    style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        border: `1px solid ${C.borderStrong}`, background: C.surfaceWarm,
                        padding: '3px 8px', fontSize: 11, color: C.ink,
                    }}
                >
                    {chip.label}
                    <button
                        onClick={chip.onClear}
                        aria-label={`Clear ${chip.label}`}
                        style={{ border: 'none', background: 'transparent', padding: 0, marginLeft: 2, cursor: 'pointer', color: C.faint, fontSize: 10 }}
                    >
                        ✕
                    </button>
                </span>
            ))}
            {onClearAll && (
                <button
                    onClick={onClearAll}
                    style={{ marginLeft: 2, border: 'none', background: 'transparent', cursor: 'pointer', fontFamily: MONO, fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase', color: C.greenDeep }}
                >
                    Clear filters
                </button>
            )}
            <span style={{ fontSize: 11, color: C.muted, marginLeft: 4 }}>
                {loading ? '…' : `${(totalCases || 0).toLocaleString()} case${totalCases === 1 ? '' : 's'}`}
            </span>
        </div>
    );
}
