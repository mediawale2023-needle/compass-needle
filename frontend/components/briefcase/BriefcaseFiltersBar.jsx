'use client';

import { briefcaseFonts, briefcasePalette as P, BriefcaseIcon, TABS } from '@/components/briefcase/briefcase-shared';

const { mono: MONO } = briefcaseFonts;

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
            <div className="md:hidden">
                <div
                    className="overflow-x-auto"
                    style={{
                        padding: '0 14px',
                        borderBottom: `1px solid ${P.hair}`,
                        background: P.paper,
                    }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 'max-content' }}>
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
                                        padding: '12px 10px',
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: 6,
                                        color: isActive ? P.ink : P.ink2,
                                        borderBottom: isActive ? `2px solid ${tab.accent || P.green}` : '2px solid transparent',
                                        marginBottom: -1,
                                        fontSize: 12,
                                        fontWeight: isActive ? 600 : 500,
                                        whiteSpace: 'nowrap',
                                    }}
                                >
                                    {tab.label}
                                    <span style={{ fontFamily: MONO, fontSize: 9.5, color: isActive ? (tab.accent || P.green) : P.ink3 }}>
                                        {(tabCounts?.[tab.countKey] || 0).toLocaleString()}
                                    </span>
                                </button>
                            );
                        })}
                    </div>
                </div>

                <div
                    style={{
                        padding: '12px 14px',
                        borderBottom: `1px solid ${P.hair}`,
                        background: P.surface,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 10,
                    }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        {[
                            { label: 'Critical', active: criticalOnly, onClick: () => onCriticalOnlyChange(!criticalOnly), count: null },
                            { label: 'New', active: statusFilter === 'new', onClick: () => onTabChange('new'), count: tabCounts?.new },
                            { label: 'Needs you', active: statusFilter === 'needs', onClick: () => onTabChange('needs'), count: tabCounts?.needs },
                        ].map((chip) => (
                            <button
                                key={chip.label}
                                onClick={chip.onClick}
                                style={{
                                    padding: '6px 10px',
                                    background: chip.active ? P.ink : 'transparent',
                                    color: chip.active ? P.paper : P.ink2,
                                    border: `1px solid ${chip.active ? P.ink : P.hair}`,
                                    fontSize: 11.5,
                                    cursor: 'pointer',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 6,
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                {chip.label}
                                {chip.count != null && <span style={{ fontFamily: MONO, fontSize: 9.5 }}>{chip.count}</span>}
                            </button>
                        ))}
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
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 5,
                                }}
                            >
                                <BriefcaseIcon name={tab.key === 'clusters' ? 'cluster' : 'eye'} size={11} color={statusFilter === tab.key ? P.paper : P.ink2} />
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    {statusFilter !== 'deleted' && (
                        <>
                            <div className="grid grid-cols-2 gap-2">
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
                                            width: '100%',
                                            padding: '8px 9px',
                                            background: P.paper,
                                            border: `1px solid ${P.hair}`,
                                            fontSize: 11.5,
                                            color: P.ink2,
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
                            </div>

                            <div className="grid grid-cols-2 gap-2">
                                <input
                                    type="date"
                                    value={dateFrom}
                                    onChange={(event) => onDateFromChange(event.target.value)}
                                    style={{
                                        width: '100%',
                                        padding: '8px 9px',
                                        border: `1px solid ${P.hair}`,
                                        background: P.paper,
                                        fontSize: 11,
                                        fontFamily: MONO,
                                        color: P.ink,
                                    }}
                                />
                                <input
                                    type="date"
                                    value={dateTo}
                                    onChange={(event) => onDateToChange(event.target.value)}
                                    style={{
                                        width: '100%',
                                        padding: '8px 9px',
                                        border: `1px solid ${P.hair}`,
                                        background: P.paper,
                                        fontSize: 11,
                                        fontFamily: MONO,
                                        color: P.ink,
                                    }}
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-2">
                                <select
                                    value={sortOrder}
                                    onChange={(event) => onSortOrderChange(event.target.value)}
                                    style={{
                                        width: '100%',
                                        border: `1px solid ${P.hair}`,
                                        background: P.paper,
                                        padding: '8px 9px',
                                        fontSize: 11.5,
                                        color: P.ink,
                                    }}
                                >
                                    <option value="newest">Newest first</option>
                                    <option value="oldest">Oldest first</option>
                                    <option value="updated">Recently updated</option>
                                    <option value="critical">Critical first</option>
                                </select>
                                <select
                                    value={pageSize}
                                    onChange={(event) => onPageSizeChange(Number(event.target.value))}
                                    style={{
                                        width: '100%',
                                        border: `1px solid ${P.hair}`,
                                        background: P.paper,
                                        padding: '8px 9px',
                                        fontSize: 11.5,
                                        color: P.ink,
                                    }}
                                >
                                    {[25, 50, 100].map((count) => (
                                        <option key={count} value={count}>{count} per page</option>
                                    ))}
                                </select>
                            </div>

                            <div className="grid grid-cols-2 gap-2">
                                <button
                                    onClick={onRefresh}
                                    style={mobileActionButton}
                                >
                                    <BriefcaseIcon name="refresh" size={11} color={P.ink2} /> Refresh
                                </button>
                                <button
                                    onClick={onExport}
                                    style={mobileActionButton}
                                >
                                    <BriefcaseIcon name="download" size={11} color={P.ink2} /> Export
                                </button>
                            </div>
                            <button onClick={onClear} style={{ ...mobileActionButton, justifyContent: 'center' }}>
                                Clear filters
                            </button>
                        </>
                    )}
                </div>
            </div>

            <div
                className="hidden md:flex"
                style={{
                    alignItems: 'center',
                    gap: 0,
                    padding: '0 22px',
                    borderBottom: `1px solid ${P.hair}`,
                    background: P.paper,
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
                <div style={{ flex: 1 }} />
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0' }}>
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
                    className="hidden md:flex"
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
                            { label: 'New', active: statusFilter === 'new', onClick: () => onTabChange('new'), count: tabCounts?.new },
                            { label: 'Needs you', active: statusFilter === 'needs', onClick: () => onTabChange('needs'), count: tabCounts?.needs },
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
                            <span style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.1em', textTransform: 'uppercase', marginLeft: 4 }}>Show</span>
                            <select
                                value={pageSize}
                                onChange={(event) => onPageSizeChange(Number(event.target.value))}
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
                                {[25, 50, 100].map((count) => (
                                    <option key={count} value={count}>{count}</option>
                                ))}
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
                                    border: `1px dashed ${P.hairStrong}`,
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

const mobileActionButton = {
    padding: '8px 10px',
    background: P.surfaceWarm,
    border: `1px solid ${P.hair}`,
    fontSize: 11.5,
    color: P.ink2,
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
};
