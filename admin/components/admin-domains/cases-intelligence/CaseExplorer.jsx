'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { apiGet } from '@/lib/api';
import {
    CASE_PRESETS,
    PERIOD_OPTIONS,
    activePreset,
    caseAge,
    caseLocation,
    casePriorityMeta,
    caseStatusMeta,
    explorerQuery,
    filtersFromParams,
    humanize,
    neighbourIds,
    searchCases,
} from '@/lib/admin-data';
import {
    Avatar,
    Badge,
    EmptyState,
    ErrorState,
    FilterSelect,
    LoadingSkeleton,
    SearchInput,
    SegmentedControl,
    SplitView,
    useMediaQuery,
} from '@/components/admin-ui';
import CaseInvestigation from './CaseInvestigation';

const EXPLORER_ROW_LIMIT = 200; // admin_api.case_explorer returns the newest 200 matches

function PriorityGlyph({ priority }) {
    return (
        <span className="nx-cx-prio" data-tone={priority.tone} data-bars={priority.bars} role="img" aria-label={`${priority.label} priority`} title={`${priority.label} priority`}>
            <i /><i /><i />
        </span>
    );
}

function CaseRow({ row, selected, onSelect, now }) {
    const priority = casePriorityMeta(row.priority, row.critical);
    const status = caseStatusMeta(row.status);
    const age = caseAge(row.created_at, row.status, now);
    const place = caseLocation(row);
    const assignee = row.assigned_to ? row.assigned_to.replace(/[._-]+/g, ' ') : null;
    return (
        <li>
            <button
                type="button"
                className="nx-cx-row"
                data-selected={selected ? 'true' : undefined}
                aria-current={selected ? 'true' : undefined}
                onClick={() => onSelect(row.id)}
            >
                <PriorityGlyph priority={priority} />
                <span className="nx-cx-row-main">
                    <span className="nx-cx-row-title">
                        <span className="nx-cx-id">#{row.id}</span>
                        <span className="nx-cx-excerpt">{row.message || 'No message text'}</span>
                    </span>
                    <span className="nx-cx-row-meta">
                        {row.critical && <><span className="nx-cx-crit">Critical</span><span className="nx-sep" aria-hidden="true">·</span></>}
                        {row.is_deleted && <><span className="nx-cx-deleted">Deleted</span><span className="nx-sep" aria-hidden="true">·</span></>}
                        <span>{row.mp}</span>
                        {place && <><span className="nx-sep" aria-hidden="true">·</span><span>{place}</span></>}
                        {row.category && row.category !== '-' && <><span className="nx-sep" aria-hidden="true">·</span><span>{row.category}</span></>}
                    </span>
                </span>
                <span className="nx-cx-row-status">
                    <Badge tone={status.tone}>{status.label}</Badge>
                    <span className="nx-cx-assignee-text">{row.assigned_to ? `Assigned · ${row.assigned_to}` : 'Unassigned'}</span>
                </span>
                <span className="nx-cx-age" data-tone={age.tone} title={row.created ? `Created ${row.created} UTC` : undefined}>
                    <span className="nx-sr-only">Age </span>{age.label}
                </span>
                <span className="nx-cx-who">
                    {assignee
                        ? <><Avatar name={assignee} size="sm" title={`Assigned to ${row.assigned_to}`} /><span className="nx-sr-only">Assigned to {row.assigned_to}</span></>
                        : <span className="nx-cx-unassigned" title="Unassigned"><span className="nx-sr-only">Unassigned</span></span>}
                </span>
            </button>
        </li>
    );
}

export default function CaseExplorer() {
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const desktop = useMediaQuery('(min-width: 1024px)');

    const [filters, setFilters] = useState(() => filtersFromParams(searchParams));
    const [selectedId, setSelectedId] = useState(() => searchParams.get('case') || null);
    const [query, setQuery] = useState('');
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [now] = useState(() => new Date());
    const requestRef = useRef(0);

    // Keep filters + selection in the URL so investigations are linkable.
    useEffect(() => {
        const params = new URLSearchParams(explorerQuery(filters).slice(1));
        if (selectedId) params.set('case', String(selectedId));
        const next = params.toString();
        const current = searchParams.toString();
        if (next !== current) router.replace(`${pathname}${next ? `?${next}` : ''}`, { scroll: false });
    }, [filters, selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

    const load = useCallback(() => {
        const request = requestRef.current + 1;
        requestRef.current = request;
        setLoading(true);
        setError('');
        apiGet(`/api/admin/cases/explorer${explorerQuery(filters)}`)
            .then((result) => { if (requestRef.current === request) setData(result); })
            .catch((e) => { if (requestRef.current === request) setError(e.message || 'Failed to load cases'); })
            .finally(() => { if (requestRef.current === request) setLoading(false); });
    }, [filters]);

    useEffect(() => { load(); }, [load]);

    const rows = useMemo(() => searchCases(data?.cases || [], query), [data, query]);

    // On desktop the investigation pane is always visible, so open the first
    // case when nothing is selected. On phones the list leads.
    useEffect(() => {
        if (desktop && !selectedId && rows.length) setSelectedId(String(rows[0].id));
    }, [desktop, rows, selectedId]);

    const setFilter = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
    const applyPreset = (value) => {
        const preset = CASE_PRESETS.find((item) => item.value === value);
        if (preset) setFilters((current) => ({ ...current, ...preset.filters }));
    };
    const clearAll = () => {
        setFilters({ mp_id: '', period: '', category: '', status: '', priority: '', assignment: '' });
        setQuery('');
    };

    const options = data?.filter_options || {};
    const total = Number(data?.total || 0);
    const loaded = data?.cases?.length || 0;
    const preset = activePreset(filters);
    const hasFilters = Object.values(filters).some(Boolean) || query;
    const { previous, next } = neighbourIds(rows, selectedId);
    const selectedRow = rows.find((row) => String(row.id) === String(selectedId)) || (data?.cases || []).find((row) => String(row.id) === String(selectedId));

    const master = (
        <section className="nx-card nx-cx-master" aria-label="Case list">
            <div className="nx-cx-toolbar">
                <SearchInput label="Search loaded cases" value={query} onChange={setQuery} placeholder="Case ID, message, account, place or phone" />
                <SegmentedControl label="Case presets" options={CASE_PRESETS.map(({ value, label }) => ({ value, label }))} value={preset} onChange={applyPreset} />
            </div>
            <div className="nx-cx-filters" role="group" aria-label="Case filters">
                <FilterSelect label="Account" value={filters.mp_id} onChange={(value) => setFilter('mp_id', value)} options={(options.mps || []).map((mp) => ({ value: String(mp.id), label: mp.constituency ? `${mp.name} · ${mp.constituency}` : mp.name }))} />
                <FilterSelect label="Period" value={filters.period} onChange={(value) => setFilter('period', value)} options={PERIOD_OPTIONS} allLabel="Any" />
                <FilterSelect label="Category" value={filters.category} onChange={(value) => setFilter('category', value)} options={(options.categories || []).map((value) => ({ value, label: value }))} />
                <FilterSelect label="Status" value={filters.status} onChange={(value) => setFilter('status', value)} options={(options.statuses || []).map((value) => ({ value, label: caseStatusMeta(value).label }))} />
                <FilterSelect label="Priority" value={filters.priority} onChange={(value) => setFilter('priority', value)} options={(options.priorities || ['critical', 'high', 'standard', 'low']).map((value) => ({ value, label: humanize(value) }))} allLabel="Any" />
                {/* "Unassigned" is a preset; an "assigned" link-in stays visible and clearable. */}
                {filters.assignment === 'assigned' && <FilterSelect label="Assignment" value={filters.assignment} onChange={(value) => setFilter('assignment', value)} options={[{ value: 'assigned', label: 'Assigned' }, { value: 'unassigned', label: 'Unassigned' }]} allLabel="Any" />}
                {hasFilters && <button type="button" className="nx-link-button" onClick={clearAll}>Clear all</button>}
            </div>
            <div className="nx-cx-listhead" aria-live="polite">
                <span>
                    {data ? (
                        query
                            ? `${rows.length} of ${loaded} loaded ${loaded === 1 ? 'case' : 'cases'} match “${query}”`
                            : `${total.toLocaleString('en-IN')} ${total === 1 ? 'case' : 'cases'}${total > loaded ? ` · showing newest ${loaded}` : ''}`
                    ) : 'Cases'}
                </span>
                <span>Newest first</span>
            </div>

            {error && <div className="nx-cx-pad"><ErrorState message={error} onRetry={load} /></div>}
            {loading && !data && <div className="nx-cx-pad"><LoadingSkeleton rows={8} label="Loading cases" /></div>}
            {data && !rows.length && !error && (
                <div className="nx-cx-pad">
                    <EmptyState
                        title={query ? 'No loaded cases match this search' : 'No cases match these filters'}
                        description={query ? 'Search covers the cases currently loaded. Narrow the filters to reach older cases.' : 'Try a different account, period or status.'}
                        action={hasFilters ? <button type="button" className="nx-btn nx-btn-sm" onClick={clearAll}>Clear filters</button> : null}
                    />
                </div>
            )}
            {rows.length > 0 && (
                <ul className="nx-cx-list" aria-label="Cases" aria-busy={loading ? 'true' : undefined}>
                    {rows.map((row) => (
                        <CaseRow key={row.id} row={row} now={now} selected={String(row.id) === String(selectedId)} onSelect={(id) => setSelectedId(String(id))} />
                    ))}
                </ul>
            )}
            {data && total > EXPLORER_ROW_LIMIT && !query && (
                <p className="nx-cx-foot">Only the newest {EXPLORER_ROW_LIMIT} matching cases load at once. Filter by account, period or status to reach older cases.</p>
            )}
        </section>
    );

    const detail = selectedId ? (
        <CaseInvestigation
            key={selectedId}
            caseId={selectedId}
            row={selectedRow}
            now={now}
            onClose={() => setSelectedId(null)}
            onPrevious={previous ? () => setSelectedId(String(previous)) : null}
            onNext={next ? () => setSelectedId(String(next)) : null}
        />
    ) : (
        <div className="nx-card nx-cx-detail-empty">
            <EmptyState title="Select a case to investigate" description="Its record, timeline, government routing and messages open here." />
        </div>
    );

    return (
        <SplitView
            master={master}
            detail={detail}
            detailLabel={selectedId ? `Case ${selectedId} investigation` : 'Case investigation'}
            detailOpen={Boolean(selectedId)}
            onCloseDetail={desktop ? undefined : () => setSelectedId(null)}
        />
    );
}
