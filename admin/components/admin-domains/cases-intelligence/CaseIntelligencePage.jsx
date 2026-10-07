'use client';

import { Suspense, useEffect, useState } from 'react';
import { apiGet } from '@/lib/api';
import { caseStatusMeta } from '@/lib/admin-data';
import {
    Badge,
    BarList,
    Card,
    DataState,
    DataTable,
    LoadingSkeleton,
    LocalTabs,
    Metric,
    MetricGroup,
    PageBand,
    Sparkline,
} from '@/components/admin-ui';
import { CASE_OPERATIONS_ITEMS } from '@/components/admin-ui/DomainNavs';
import CaseExplorer from './CaseExplorer';
import '@/app/styles/admin-cases.css';

const VIEWS = [
    { key: 'explorer', label: 'Cases' },
    { key: 'analytics', label: 'Analytics' },
    { key: 'health', label: 'Case health' },
];

const VIEW_COPY = {
    explorer: 'Investigate citizen grievances across every account. Admin is read-only here; cases are worked by MP staff.',
    analytics: 'Category, status and resolution patterns across all accounts.',
    health: 'Case volume and account activity across the platform.',
};

export default function CaseIntelligencePage() {
    const [view, setView] = useState('explorer');

    return (
        <div className="nx-cases" data-view={view}>
            <PageBand
                title="Case Explorer"
                description={VIEW_COPY[view]}
                tabs={<LocalTabs label="Case Operations" items={CASE_OPERATIONS_ITEMS} />}
                actions={(
                    <div className="nx-seg nx-cases-views" role="group" aria-label="Case view">
                        {VIEWS.map((item) => (
                            <button
                                key={item.key}
                                type="button"
                                className="nx-seg-option"
                                aria-pressed={view === item.key}
                                data-selected={view === item.key ? 'true' : undefined}
                                onClick={() => setView(item.key)}
                            >
                                {item.label}
                            </button>
                        ))}
                    </div>
                )}
            />

            {view === 'explorer' && (
                <Suspense fallback={<LoadingSkeleton rows={8} label="Loading cases" />}>
                    <CaseExplorer />
                </Suspense>
            )}
            {view === 'analytics' && <GrievanceAnalytics />}
            {view === 'health' && <CaseHealth />}
        </div>
    );
}

function useAdminData(path) {
    const [state, setState] = useState({ data: null, error: '', loading: true });
    const load = () => {
        setState((current) => ({ ...current, loading: true, error: '' }));
        apiGet(path)
            .then((data) => setState({ data, error: '', loading: false }))
            .catch((e) => setState({ data: null, error: e.message || 'Failed to load', loading: false }));
    };
    useEffect(load, [path]); // eslint-disable-line react-hooks/exhaustive-deps
    return { ...state, reload: load };
}

function fmt(value) {
    return value === null || value === undefined ? null : Number(value).toLocaleString('en-IN');
}

/* ═══ Case health (/api/admin/cases/health) ═══ */
function CaseHealth() {
    const { data, error, loading, reload } = useAdminData('/api/admin/cases/health');
    return (
        <DataState loading={loading} error={error} onRetry={reload} rows={6}>
            {data && (
                <div className="nx-cases-stack">
                    <Card padded>
                        <MetricGroup columns={4}>
                            <Metric label="Total cases" value={fmt(data.total_cases)} unavailable={data.total_cases == null} />
                            <Metric label="Active accounts" value={fmt(data.active_mps)} unavailable={data.active_mps == null} />
                            <Metric label="Resolved" value={fmt(data.resolved)} tone="ok" unavailable={data.resolved == null} />
                            <Metric label="Critical" value={fmt(data.critical)} tone={data.critical ? 'critical' : undefined} unavailable={data.critical == null} />
                        </MetricGroup>
                    </Card>
                    <div className="nx-cases-grid">
                        <Card title="Cases by status">
                            <div className="nx-cases-pad">
                                <DataState empty={!data.status_breakdown?.length} emptyTitle="No cases yet">
                                    <BarList items={(data.status_breakdown || []).map((s) => ({ label: caseStatusMeta(s.status).label, value: s.count }))} />
                                </DataState>
                            </div>
                        </Card>
                        <Card title="Cases per account" description="Top 10 by volume">
                            <div className="nx-cases-pad">
                                <DataState empty={!data.mp_cases?.length} emptyTitle="No cases yet">
                                    <BarList items={(data.mp_cases || []).slice(0, 10).map((m) => ({ label: m.name, value: m.cases }))} />
                                </DataState>
                            </div>
                        </Card>
                    </div>
                    <Card title="Case volume" description="New cases per day, last 30 days">
                        <div className="nx-cases-pad">
                            <DataState empty={!data.volume_30d?.length} emptyTitle="No cases in the last 30 days">
                                <Sparkline values={(data.volume_30d || []).map((v) => Number(v.count) || 0)} width={640} height={96} area label="New cases per day, last 30 days" />
                            </DataState>
                        </div>
                    </Card>
                    <Card title="Account activity">
                        <DataTable
                            label="Account activity"
                            rows={data.activity || []}
                            getRowKey={(row, index) => `${row.mp}-${index}`}
                            empty={<div className="nx-cases-pad"><DataState empty emptyTitle="No accounts yet" /></div>}
                            columns={[
                                { key: 'mp', header: 'Account', render: (row) => <strong>{row.mp}</strong> },
                                { key: 'constituency', header: 'Constituency', hideBelow: 'md' },
                                { key: 'cases', header: 'Cases', align: 'right', render: (row) => fmt(row.cases) },
                                { key: 'last_login', header: 'Last login', hideBelow: 'md' },
                                { key: 'active', header: 'Status', render: (row) => <Badge tone={row.active ? 'ok' : 'neutral'}>{row.active ? 'Active' : 'Never logged in'}</Badge> },
                            ]}
                        />
                    </Card>
                </div>
            )}
        </DataState>
    );
}

/* ═══ Grievance analytics (/api/admin/cases/analytics/data) ═══ */
function GrievanceAnalytics() {
    const { data, error, loading, reload } = useAdminData('/api/admin/cases/analytics/data');
    return (
        <DataState loading={loading} error={error} onRetry={reload} rows={6}>
            {data && (
                <div className="nx-cases-stack">
                    <Card title="Most common grievance categories" description="By account constituency">
                        <div className="nx-cases-pad">
                            <DataState empty={!data.category_breakdown?.length} emptyTitle="No categorised cases yet">
                                <BarList items={(data.category_breakdown || []).slice(0, 12).map((c, i) => ({ label: `${c.category} · ${c.constituency}`, value: c.count, key: i }))} />
                            </DataState>
                        </div>
                    </Card>
                    <div className="nx-cases-grid">
                        <Card title="Category volume" description="All accounts">
                            <DataTable
                                label="Category volume"
                                rows={data.category_volume || []}
                                getRowKey={(row) => row.category}
                                empty={<div className="nx-cases-pad"><DataState empty emptyTitle="No categories yet" /></div>}
                                columns={[
                                    { key: 'category', header: 'Category' },
                                    { key: 'count', header: 'Cases', align: 'right', render: (row) => fmt(row.count) },
                                ]}
                            />
                        </Card>
                        <Card title="Status distribution">
                            <DataTable
                                label="Status distribution"
                                rows={data.status_distribution || []}
                                getRowKey={(row) => row.status}
                                empty={<div className="nx-cases-pad"><DataState empty emptyTitle="No cases yet" /></div>}
                                columns={[
                                    { key: 'status', header: 'Status', render: (row) => { const meta = caseStatusMeta(row.status); return <Badge tone={meta.tone}>{meta.label}</Badge>; } },
                                    { key: 'count', header: 'Cases', align: 'right', render: (row) => fmt(row.count) },
                                ]}
                            />
                        </Card>
                    </div>
                    <Card title="Average resolution time" description="Per account, from resolved cases">
                        <DataTable
                            label="Average resolution time"
                            rows={data.resolution_times || []}
                            getRowKey={(row, index) => `${row.mp}-${index}`}
                            empty={<div className="nx-cases-pad"><DataState empty emptyTitle="No resolution data available yet" /></div>}
                            columns={[
                                { key: 'mp', header: 'Account', render: (row) => <strong>{row.mp}</strong> },
                                { key: 'constituency', header: 'Constituency', hideBelow: 'md' },
                                { key: 'resolved_cases', header: 'Resolved', align: 'right', render: (row) => fmt(row.resolved_cases) },
                                { key: 'avg_resolution_time', header: 'Average time', align: 'right' },
                            ]}
                        />
                    </Card>
                    <Card title="Cases by assembly constituency" description="Top 15">
                        <div className="nx-cases-pad">
                            <DataState empty={!data.assembly_distribution?.length} emptyTitle="No assembly data yet">
                                <BarList items={(data.assembly_distribution || []).slice(0, 15).map((a) => ({ label: a.assembly, value: a.cases }))} />
                            </DataState>
                        </div>
                    </Card>
                </div>
            )}
        </DataState>
    );
}
