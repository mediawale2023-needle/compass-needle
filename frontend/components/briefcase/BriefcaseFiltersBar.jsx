'use client';

import { briefcasePalette as BASE_P, BriefcaseIcon, TABS } from '@/components/briefcase/briefcase-shared';

const MONO = '"IBM Plex Mono", ui-monospace, SFMono-Regular, monospace';

// Retint the legacy briefcase palette onto the approved Overview / Case Detail
// visual system without rewriting every usage.
const P = {
    ...BASE_P,
    paper: '#F3EEE2',
    surface: '#FFFEFB',
    surfaceWarm: '#F8F1E0',
    hair: '#E4DECB',
    hairStrong: '#C9BFA9',
    ink: '#211F19',
    ink2: '#4A453A',
    ink3: '#6C6858',
    green: '#2B6E4C',
    greenDeep: '#245F45',
    saffron: '#BC6A36',
    saffronTint: '#F1DED0',
};

export default function BriefcaseFiltersBar(props) {
    const {
        assignedFilter,
        assemblyFilter,
        categoryFilter,
        criticalOnly,
        dateFrom,
        dateTo,
        filterOptions,
        onAssemblyChange,
        onAssignedChange,
        onCategoryChange,
        onClear,
        onCriticalOnlyChange,
        onDateFromChange,
        onDateToChange,
        onExport,
        onLocationChange,
        onPageSizeChange,
        onRefresh,
        onSortOrderChange,
        onTabChange,
        optionLabel,
        pageSize,
        sortOrder,
        staff,
        statusFilter,
        locationFilter,
        tabCounts,
    } = props;

    const primaryTabs = TABS.filter((tab) => !['clusters', 'deleted'].includes(tab.key));
    const auxiliaryTabs = TABS.filter((tab) => ['clusters', 'deleted'].includes(tab.key));

    return (
        <>
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0,
                    padding: '0 22px',
                    borderBottom: `1px solid ${P.hair}`,
                    background: P.paper,
                    overflowX: 'auto',
                    whiteSpace: 'nowrap',
                }}
            >
                {primaryTabs.map((tab) => {
                    const isActive = statusFilter === tab.key;
                    return (
                        <button
                            key={tab.key}
                            onClick={() => onTabChange(tab.key)}
                            style={{
                                border: 'none',
                                background: 'transparent',
                                cursor: 'pointer',
                                padding: '12px 16px',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 7,
                                flexShrink: 0,
                                fontFamily: 'inherit',
                                color: isActive ? P.ink : P.ink2,
                                borderBottom: isActive ? `2px solid ${tab.accent || P.green}` : '2px solid transparent',
                                marginBottom: -1,
                                fontSize: 13,
                                fontWeight: isActive ? 600 : 500,
                            }}
                        >
                            {tab.label}
                            <span
                                style={{
                                    fontFamily: MONO,
                                    fontSize: 10,
                                    color: isActive ? (tab.accent || P.green) : P.ink3,
                                    background: isActive && tab.accent ? P.saffronTint : 'transparent',
                                    padding: isActive && tab.accent ? '1px 5px' : 0,
                                    fontWeight: 600,
                                }}
                            >
                                {(tabCounts?.[tab.countKey] || 0).toLocaleString()}
                            </span>
                        </button>
                    );
                })}
                <div style={{ flex: 1, minWidth: 12 }} />
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', flexShrink: 0 }}>
                    {auxiliaryTabs.map((tab) => (
                        <button
                            key={tab.key}
                            onClick={() => onTabChange(tab.key)}
                            style={{
                                padding: '6px 10px',
                                background: statusFilter === tab.key ? P.ink : 'transparent',
                                color: statusFilter === tab.key ? P.paper : P.ink2,
                                border: `1px solid ${P.hair}`,
                                fontSize: 11,
                                cursor: 'pointer',
                                fontFamily: 'inherit',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 5,
                                flexShrink: 0,
                            }}
                        >
                            <BriefcaseIcon name={tab.key === 'clusters' ? 'cluster' : 'eye'} size={11} color={statusFilter === tab.key ? P.paper : P.ink2} />
                            {tab.label}
                        </button>
                    ))}
                </div>
            </div>

            {statusFilter !== 'deleted' && (
                <div
                    style={{
                        padding: '12px 22px',
                        borderBottom: `1px solid ${P.hair}`,
                        background: P.surface,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 10,
                    }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span
                            style={{
                                fontFamily: MONO,
                                fontSize: 9.5,
                                color: P.ink3,
                                letterSpacing: '0.14em',
                                textTransform: 'uppercase',
                                marginRight: 4,
                            }}
                        >
                            Quick
                        </span>
                        {[
                            { label: 'Critical', active: criticalOnly, onClick: () => onCriticalOnlyChange(!criticalOnly), count: null },
                            { label: 'Today', active: !!dateFrom && dateFrom === dateTo, onClick: () => {
                                const today = new Date().toISOString().slice(0, 10);
                                onDateFromChange(today);
                                onDateToChange(today);
                            }, count: null },
                        ].map((chip) => (
                            <button
                                key={chip.label}
                                onClick={chip.onClick}
                                style={{
                                    padding: '5px 10px',
                                    background: chip.active ? P.ink : 'transparent',
                                    color: chip.active ? P.paper : P.ink2,
                                    border: `1px solid ${chip.active ? P.ink : P.hair}`,
                                    fontSize: 11.5,
                                    fontWeight: 500,
                                    cursor: 'pointer',
                                    fontFamily: 'inherit',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 6,
                                }}
                            >
                                {chip.label}
                                {chip.count != null && (
                                    <span style={{ fontFamily: MONO, fontSize: 9.5, color: chip.active ? P.paper : P.ink3 }}>
                                        {chip.count}
                                    </span>
                                )}
                            </button>
                        ))}
                        <div style={{ flex: 1 }} />
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: P.ink3 }}>
                            <span style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.1em', textTransform: 'uppercase' }}>Sort</span>
                            <select
                                value={sortOrder}
                                onChange={(event) => onSortOrderChange(event.target.value)}
                                style={{
                                    border: `1px solid ${P.hair}`,
                                    background: P.surface,
                                    padding: '4px 8px',
                                    fontSize: 11,
                                    fontFamily: 'inherit',
                                    color: P.ink,
                                    cursor: 'pointer',
                                }}
                            >
                                <option value="newest">Newest first</option>
                                <option value="oldest">Oldest first</option>
                                <option value="updated">Recently updated</option>
                                <option value="critical">Critical first</option>
                            </select>
                        </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        {[
                            ['Category', categoryFilter, onCategoryChange, filterOptions.categories],
                            ['Location', locationFilter, onLocationChange, filterOptions.locations],
                            ['Assembly', assemblyFilter, onAssemblyChange, filterOptions.assemblies],
                            ['Assignee', assignedFilter, onAssignedChange, staff.map((member) => ({ value: member.username, count: null }))],
                        ].map(([label, value, onChange, options]) => (
                            <select
                                key={label}
                                value={value}
                                onChange={(event) => onChange(event.target.value)}
                                style={{
                                    padding: '5px 10px',
                                    background: 'transparent',
                                    border: `1px solid ${P.hairStrong}`,
                                    fontSize: 11.5,
                                    color: P.ink2,
                                    cursor: 'pointer',
                                    fontFamily: 'inherit',
                                }}
                            >
                                <option value="">{label}</option>
                                {options.map((option) => (
                                    <option key={option.value} value={option.value}>
                                        {label === 'Assignee' ? option.value : optionLabel(option)}
                                    </option>
                                ))}
                            </select>
                        ))}

                        <span style={{ width: 1, height: 18, background: P.hair, margin: '0 4px' }} />
                        <span style={{ fontFamily: MONO, fontSize: 9.5, color: P.ink3, letterSpacing: '0.1em', textTransform: 'uppercase' }}>Range</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                            <input
                                type="date"
                                value={dateFrom}
                                onChange={(event) => onDateFromChange(event.target.value)}
                                style={{
                                    width: 122,
                                    padding: '4px 8px',
                                    border: `1px solid ${P.hair}`,
                                    background: P.surface,
                                    fontSize: 11,
                                    fontFamily: MONO,
                                    color: P.ink,
                                }}
                            />
                            <span style={{ color: P.ink3 }}>→</span>
                            <input
                                type="date"
                                value={dateTo}
                                onChange={(event) => onDateToChange(event.target.value)}
                                style={{
                                    width: 122,
                                    padding: '4px 8px',
                                    border: `1px solid ${P.hair}`,
                                    background: P.surface,
                                    fontSize: 11,
                                    fontFamily: MONO,
                                    color: P.ink,
                                }}
                            />
                        </div>
                        <div style={{ flex: 1 }} />
                        <button
                            onClick={onRefresh}
                            style={{
                                padding: '5px 10px',
                                background: 'transparent',
                                border: `1px solid ${P.hair}`,
                                fontSize: 11,
                                color: P.ink2,
                                cursor: 'pointer',
                                fontFamily: 'inherit',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 5,
                            }}
                        >
                            <BriefcaseIcon name="refresh" size={11} color={P.ink2} /> Refresh
                        </button>
                        <button
                            onClick={onExport}
                            style={{
                                padding: '5px 10px',
                                background: 'transparent',
                                border: `1px solid ${P.hair}`,
                                fontSize: 11,
                                color: P.ink2,
                                cursor: 'pointer',
                                fontFamily: 'inherit',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 5,
                            }}
                        >
                            <BriefcaseIcon name="download" size={11} color={P.ink2} /> Export CSV
                        </button>
                        <button
                            onClick={onClear}
                            style={{
                                padding: '5px 10px',
                                background: 'transparent',
                                border: `1px solid ${P.hair}`,
                                fontSize: 11,
                                color: P.ink2,
                                cursor: 'pointer',
                                fontFamily: 'inherit',
                            }}
                        >
                            Clear
                        </button>
                    </div>
                </div>
            )}
        </>
    );
}
