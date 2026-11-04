'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
    Activity, Bot, Briefcase, ClipboardCheck, FileText, Inbox, Landmark, Megaphone,
    MessageCircle, Plus, RefreshCw, TriangleAlert, Webhook, Workflow,
} from 'lucide-react';
import { apiGet } from '@/lib/api';
import { useAdminSignals } from '@/lib/admin-signals';
import {
    accountHealth, buildAttentionItems, caseTrend, countAttention, deriveWhatsAppIncidents, formatCount,
    formatDuration, formatRelative, openOverDays, parliamentFreshness, routingCoverage,
    SEVERITY_LABEL, severityFromHealthStatus,
} from '@/lib/admin-data';
import {
    AccountIdentity, Avatar, Badge, BarList, Card, ChartLegend, DataState, DataTable, LineChart, ListRow,
    Metric, MetricGroup, PageHeader, ProgressBar, SegmentBar, SegmentedControl, SeverityBadge, SeverityTile,
    Sparkline, StatusText, Unavailable, MobileDisclosure,
} from '@/components/admin-ui';
import { useMediaQuery } from '@/components/admin-ui/useMediaQuery';
import '@/app/styles/admin-command-centre.css';

// Every resource the Command Centre reads. Each loads independently so one
// failing source degrades only its own section.
const RESOURCES = {
    stats: '/api/admin/stats',
    accounts: '/api/admin/mps',
    alerts: '/api/admin/alerts',
    health: '/api/admin/system-health',
    inbound: '/api/admin/whatsapp/inbound?limit=1',
    jobs: '/api/admin/jobs?page=1&page_size=10',
    audit: '/api/admin/audit?days=7',
    cases: '/api/admin/cases/aggregates?weeks=12',
    activity: '/api/admin/tenant-health',
    parliament: '/api/admin/parliament/sync/status',
};

const ATTENTION_ICONS = {
    messaging: MessageCircle, job: Workflow, activity: Activity, setup: ClipboardCheck,
    announcement: Megaphone, alert: TriangleAlert,
};

function useCommandCentreData() {
    const [data, setData] = useState({});
    const [status, setStatus] = useState(() => Object.fromEntries(Object.keys(RESOURCES).map((key) => [key, 'loading'])));
    const [errors, setErrors] = useState({});

    const load = useCallback(async (key) => {
        setStatus((current) => ({ ...current, [key]: 'loading' }));
        setErrors((current) => ({ ...current, [key]: '' }));
        try {
            const result = await apiGet(RESOURCES[key]);
            setData((current) => ({ ...current, [key]: result }));
            setStatus((current) => ({ ...current, [key]: 'ready' }));
        } catch (error) {
            setErrors((current) => ({ ...current, [key]: error?.message || 'Request failed' }));
            setStatus((current) => ({ ...current, [key]: 'error' }));
        }
    }, []);

    const loadAll = useCallback(() => { Object.keys(RESOURCES).forEach(load); }, [load]);
    useEffect(() => { loadAll(); }, [loadAll]);

    return { data, status, errors, load, loadAll };
}

function accountLabel(account) {
    const name = account.display_name || account.mp_name || `Account #${account.tenant_id}`;
    const seat = account.profile?.constituency || account.parliamentary_constituency;
    const state = account.profile?.state;
    return { name, detail: [seat && seat !== 'India' ? seat : null, state].filter(Boolean).join(' · ') || null };
}

// ─── Summary ──────────────────────────────────────────────────────────────

function AttentionSummary({ counts, ready, error }) {
    const unavailable = !ready;
    return (
        <Card padded className="nx-cc-summary-card">
            <div className="nx-cc-summary-head">
                <SeverityTile tone={counts?.critical ? 'critical' : counts?.warning ? 'warning' : 'ok'} icon={TriangleAlert} />
                <h2 className="nx-card-title">Needs your attention</h2>
                <a className="nx-link nx-cc-summary-link" href="#attention">Review queue →</a>
            </div>
            <Metric
                size="lg"
                label={<span className="nx-sr-only">Issues needing action</span>}
                value={unavailable ? null : counts.total}
                unavailable={unavailable}
                detail={unavailable ? null : counts.total === 1 ? 'issue needs action' : 'issues need action'}
            />
            {error && <span className="nx-unavailable">Alerts could not be loaded</span>}
            <div className="nx-cc-severity">
                {['critical', 'warning', 'review'].map((severity) => (
                    <div key={severity} className="nx-cc-severity-cell" data-tone={severity} data-active={!unavailable && counts[severity] ? 'true' : undefined}>
                        <span className="nx-cc-severity-label"><span className="nx-dot" data-tone={severity} aria-hidden="true" />{SEVERITY_LABEL[severity]}</span>
                        <strong>{unavailable ? <Unavailable /> : counts[severity]}</strong>
                    </div>
                ))}
            </div>
        </Card>
    );
}

function AccountsSummary({ stats, accounts, whatsapp, statsReady, accountsReady }) {
    const coverage = routingCoverage(whatsapp);
    const total = statsReady ? (stats?.total_accounts ?? stats?.total_mps ?? null) : null;
    const recent = useMemo(() => {
        if (!accountsReady) return null;
        const cutoff = Date.now() - 90 * 86_400_000;
        const seen = new Set();
        return accounts.filter((account) => {
            if (seen.has(account.tenant_id)) return false;
            seen.add(account.tenant_id);
            const created = Date.parse(account.created_at);
            return Number.isFinite(created) && created >= cutoff;
        }).length;
    }, [accounts, accountsReady]);
    return (
        <Card padded tone="ok" className="nx-cc-summary-card">
            <div className="nx-cc-summary-head">
                <SeverityTile tone="forest-tile" icon={Landmark} />
                <h2 className="nx-card-title">Accounts</h2>
                {recent ? <span className="nx-badge nx-badge-plain" data-tone="ok">+{recent} in 90 days</span> : null}
            </div>
            <Metric size="lg" label={<span className="nx-sr-only">Accounts</span>} value={total === null ? null : formatCount(total)} detail="political accounts managed" />
            {coverage ? (
                <SegmentBar
                    label={`WhatsApp routing: ${coverage.configured} configured, ${coverage.misconfigured} incomplete`}
                    segments={[
                        { label: 'routing configured', value: coverage.configured, tone: 'forest' },
                        { label: 'routing incomplete', value: coverage.misconfigured, tone: 'warning' },
                    ]}
                />
            ) : <span className="nx-unavailable">WhatsApp routing coverage unavailable</span>}
        </Card>
    );
}

function CasesSummary({ stats, cases, statsReady, casesReady }) {
    const trend = casesReady ? caseTrend(cases) : null;
    const over14 = casesReady ? openOverDays(cases, 14) : null;
    const total = statsReady ? stats?.total_cases ?? null : null;
    const change = trend?.openChange;
    return (
        <Card padded tone="info" className="nx-cc-summary-card">
            <div className="nx-cc-summary-head">
                <SeverityTile tone="slate-tile" icon={Inbox} />
                <h2 className="nx-card-title">Cases</h2>
                {change !== null && change !== undefined && (
                    <span className="nx-badge nx-badge-plain" data-tone={change > 0 ? 'warning' : 'ok'}>
                        {change > 0 ? '↑' : change < 0 ? '↓' : '→'} {Math.abs(change)} vs last week
                    </span>
                )}
            </div>
            <div className="nx-cc-cases">
                <div>
                    <Metric
                        size="lg"
                        label={<span className="nx-sr-only">Open cases</span>}
                        value={casesReady ? formatCount(cases.open_now) : null}
                        detail="open"
                    />
                    <p className="nx-cc-cases-sub">
                        {total !== null ? <>of <strong>{formatCount(total)}</strong> total</> : <Unavailable>Total unavailable</Unavailable>}
                        {over14 !== null && <> · {formatCount(over14)} older than 14 days</>}
                    </p>
                </div>
                {trend && <Sparkline values={trend.openAtEnd} tone="review" area label={`Open cases at the end of each of the last ${trend.openAtEnd.length} weeks`} />}
            </div>
        </Card>
    );
}

// ─── Needs attention ──────────────────────────────────────────────────────

function AttentionAccount({ item }) {
    if (item.scope === 'platform') {
        return <span className="nx-cc-scope">{item.affected || 'Platform-wide'}</span>;
    }
    return <AccountIdentity size="sm" name={item.account?.name} detail={item.account?.detail} />;
}

function FeaturedAttention({ item }) {
    const Icon = ATTENTION_ICONS[item.icon] || TriangleAlert;
    return (
        <div className="nx-cc-featured" data-tone={item.severity}>
            <SeverityTile tone={item.severity} icon={Icon} size="lg" />
            <div className="nx-cc-featured-body">
                <div className="nx-cc-featured-meta">
                    <SeverityBadge severity={item.severity} />
                    <span className="nx-muted">{item.scope === 'platform' ? 'Platform-wide' : 'Account'}</span>
                </div>
                <div className="nx-cc-featured-title">{item.title}</div>
                <AttentionAccount item={item} />
                {item.detail && <p className="nx-cc-featured-detail">{item.detail}</p>}
            </div>
            <div className="nx-cc-featured-actions">
                {item.tenantId !== null && item.tenantId !== undefined && (
                    <Link className="nx-btn nx-btn-sm" href={`/dashboard/mps/${item.tenantId}`}>Open account</Link>
                )}
                <Link className="nx-btn nx-btn-primary nx-btn-sm" href={item.action.href}>{item.action.label}</Link>
            </div>
        </div>
    );
}

function AttentionRow({ item }) {
    const Icon = ATTENTION_ICONS[item.icon] || TriangleAlert;
    return (
        <ListRow
            leading={<SeverityTile tone={item.severity} icon={Icon} />}
            title={item.title}
            badge={<SeverityBadge severity={item.severity} />}
            meta={item.scope === 'platform' ? (item.affected || item.detail || 'Platform-wide') : [item.account?.name, item.account?.detail].filter(Boolean).join(' · ')}
            aside={item.scope === 'account' && item.detail ? <span className="nx-cc-row-detail">{item.detail}</span> : null}
            actions={<Link className="nx-btn nx-btn-sm" href={item.action.href}>{item.action.label}</Link>}
        />
    );
}

function NeedsAttention({ items, loading, error, onRetry, compact }) {
    const [filter, setFilter] = useState('all');
    const [expanded, setExpanded] = useState(false);
    const counts = countAttention(items || []);
    const visible = (items || []).filter((item) => filter === 'all' || item.severity === filter);
    const featured = filter === 'all' && visible[0] && ['critical', 'warning'].includes(visible[0].severity) ? visible[0] : null;
    const rest = featured ? visible.slice(1) : visible;
    const limit = compact ? 3 : 6;
    const shown = expanded ? rest : rest.slice(0, limit);

    return (
        <Card
            id="attention"
            title={<span className="nx-cc-title-count">Needs attention {items ? <span className="nx-count">{counts.total}</span> : null}</span>}
            description="Ranked by severity, scope and impact · from live alerts and WhatsApp health"
            actions={items && items.length > 0 ? (
                <SegmentedControl
                    label="Filter by severity"
                    value={filter}
                    onChange={setFilter}
                    options={[
                        { value: 'all', label: 'All', count: counts.total },
                        { value: 'critical', label: 'Critical', dot: 'critical', count: counts.critical || undefined },
                        { value: 'warning', label: 'Warning', dot: 'warning', count: counts.warning || undefined },
                        { value: 'review', label: 'Review', dot: 'review', count: counts.review || undefined },
                    ]}
                />
            ) : null}
        >
            <DataState
                loading={loading}
                error={error}
                onRetry={onRetry}
                rows={4}
                empty={Boolean(items) && visible.length === 0}
                emptyTitle={filter === 'all' ? 'No active alerts' : `No ${SEVERITY_LABEL[filter].toLowerCase()} items`}
                emptyDescription={filter === 'all' ? 'All alert checks completed and returned no current issues.' : 'Choose another filter to see other items.'}
            >
                {featured && <FeaturedAttention item={featured} />}
                <div className="nx-cc-rows">
                    {shown.map((item) => <AttentionRow key={item.id} item={item} />)}
                </div>
                {rest.length > limit && (
                    <div className="nx-card-foot">
                        <span>{expanded ? `Showing all ${visible.length}` : `Showing ${(featured ? 1 : 0) + shown.length} of ${visible.length}`}</span>
                        <button type="button" className="nx-btn nx-btn-ghost nx-btn-sm" onClick={() => setExpanded((value) => !value)}>
                            {expanded ? 'Show fewer' : `Show all ${visible.length}`}
                        </button>
                    </div>
                )}
            </DataState>
        </Card>
    );
}

// ─── Operational pulse ────────────────────────────────────────────────────

function PulseTile({ label, value, detail, tone, href, unavailable }) {
    return (
        <Link href={href} className="nx-cc-pulse" data-tone={tone}>
            <span className="nx-metric-label">{label}</span>
            <strong className="nx-cc-pulse-value" data-unavailable={unavailable ? 'true' : undefined}>{unavailable ? 'Unavailable' : value}</strong>
            {detail && !unavailable && <span className="nx-cc-pulse-detail">{detail}</span>}
        </Link>
    );
}

function OperationalPulse({ inbound, health, jobs, status }) {
    const summary = inbound?.summary || health?.whatsapp?.webhook?.inbound_queue || null;
    const outbound = health?.whatsapp?.outbound || null;
    const routing = health?.whatsapp?.routing || null;
    const jobSummary = jobs?.summary || null;
    const inboundReady = Boolean(summary);
    const queued = inboundReady ? Number(summary.received_count || 0) + Number(summary.processing_count || 0) : null;
    const stuck = inboundReady ? Number(summary.stale_received_count || 0) + Number(summary.stale_processing_count || 0) : null;
    const failedIn = inboundReady ? Number(summary.failed_count || 0) : null;
    const lastWebhook = summary?.last_webhook ? formatRelative(summary.last_webhook) : null;
    const failedOut = outbound ? Number(outbound.failed_outbound_24h || 0) : null;
    const sentOut = outbound ? Number(outbound.sent_outbound_24h || 0) : null;
    const attempts = outbound ? failedOut + sentOut : 0;

    return (
        <Card title="Operational pulse" description="Messaging, processing and background work · live">
            <div className="nx-cc-pulse-grid">
                <PulseTile label="Inbound queued" value={formatCount(queued)} detail={stuck ? `${stuck} stuck` : `Webhook ${lastWebhook || 'not recorded'}`} tone={stuck ? 'warning' : 'neutral'} href="/dashboard/system/whatsapp-inbound" unavailable={!inboundReady} />
                <PulseTile label="Inbound failed" value={formatCount(failedIn)} detail={failedIn ? 'Need retry or review' : 'No failed inbound'} tone={failedIn ? 'critical' : 'neutral'} href="/dashboard/system/whatsapp-inbound" unavailable={!inboundReady} />
                <PulseTile label="Outbound failed" value={formatCount(failedOut)} detail={outbound ? `Last 24h · ${formatCount(sentOut)} sent` : null} tone={failedOut ? 'critical' : 'neutral'} href="/dashboard/system/whatsapp#failures" unavailable={!outbound} />
                <PulseTile label="Failed jobs" value={formatCount(jobSummary?.failed)} detail={jobSummary ? `All recorded runs · ${jobSummary.running} running` : null} tone={jobSummary?.failed ? 'warning' : 'neutral'} href="/dashboard/system/jobs" unavailable={!jobSummary} />
            </div>
            <div className="nx-cc-pulse-foot">
                <div className="nx-cc-bar">
                    <div className="nx-cc-bar-row"><span>WhatsApp routing configured</span><strong>{routing ? <>{routing.configured_tenants} <span className="nx-muted">/ {routing.active_tenants}</span></> : <Unavailable />}</strong></div>
                    {routing && <ProgressBar value={routing.configured_tenants} max={Math.max(routing.active_tenants, 1)} tone={routing.misconfigured_tenants ? 'warning' : 'forest'} label="WhatsApp routing configured" />}
                </div>
                <div className="nx-cc-bar">
                    <div className="nx-cc-bar-row"><span>Outbound delivered · 24h</span><strong>{outbound ? (attempts ? <>{formatCount(sentOut)} <span className="nx-muted">of {formatCount(attempts)} · {Math.round((sentOut / attempts) * 100)}%</span></> : <span className="nx-muted">No sends in 24h</span>) : <Unavailable />}</strong></div>
                    {outbound && attempts > 0 && <ProgressBar value={sentOut} max={attempts} tone={failedOut ? 'warning' : 'ok'} label="Outbound delivered in 24 hours" />}
                </div>
            </div>
            {(status.inbound === 'loading' && status.health === 'loading') && <span className="nx-sr-only" aria-live="polite">Loading operational pulse</span>}
        </Card>
    );
}

// ─── Case analytics ───────────────────────────────────────────────────────

function CaseFlow({ cases, loading, error, onRetry }) {
    const trend = cases ? caseTrend(cases) : null;
    const median = cases ? formatDuration(cases.resolution?.median_hours) : null;
    return (
        <Card
            title="Case intake vs resolution"
            description="Weekly, all accounts · completed weeks"
            actions={<ChartLegend items={[{ label: 'New cases', tone: 'forest' }, { label: 'Resolved', tone: 'mint' }]} />}
        >
            <DataState loading={loading} error={error} onRetry={onRetry} rows={5} empty={Boolean(cases) && !trend} emptyTitle="No case activity in this period">
                {trend && (
                    <div className="nx-cc-flow">
                        <MetricGroup columns={3}>
                            <Metric label="Median time to resolve" value={median} unavailable={!median} detail={median ? `${formatCount(cases.resolution.resolved_in_window)} resolved in 12 weeks` : null} />
                            <Metric label="This week so far" value={`${trend.thisWeek.new} new`} detail={`${trend.thisWeek.resolved} resolved`} />
                            <Metric label="Open, since last week" value={trend.openChange === null ? null : `${trend.openChange > 0 ? '+' : ''}${trend.openChange}`} tone={trend.openChange > 0 ? 'warning' : undefined} detail={`${formatCount(cases.open_now)} open now`} />
                        </MetricGroup>
                        {trend.labels.length >= 2 ? <LineChart
                            ariaLabel={`Weekly new and resolved cases over ${trend.labels.length} weeks`}
                            labels={trend.labels}
                            series={[{ label: 'New cases', values: trend.newCases, tone: 'forest' }, { label: 'Resolved', values: trend.resolved, tone: 'mint' }]}
                        /> : <p className="nx-cc-footnote">Weekly trend appears after two completed weeks.</p>}
                    </div>
                )}
            </DataState>
        </Card>
    );
}

const AGE_TONES = ['forest', 'forest-2', 'forest-3', 'warning', 'critical'];

function CaseAgeing({ cases, loading, error, onRetry }) {
    const bands = cases?.ageing || [];
    const total = bands.reduce((sum, band) => sum + Number(band.count || 0), 0);
    return (
        <Card
            title="Case ageing"
            description={cases ? `${formatCount(cases.open_now)} open cases by age` : 'Open cases by age'}
            actions={<Link className="nx-link" href="/dashboard/cases-intelligence/explorer">Open cases →</Link>}
        >
            <div className="nx-cc-pad">
                <DataState loading={loading} error={error} onRetry={onRetry} rows={5} empty={Boolean(cases) && total === 0} emptyTitle="No open cases">
                    <BarList items={bands.map((band, index) => ({ label: band.label, value: band.count, tone: AGE_TONES[index] || 'forest' }))} />
                    <p className="nx-cc-footnote">Age since the case was created. Bands are for reading only — Needle defines no resolution deadline.</p>
                </DataState>
            </div>
        </Card>
    );
}

// ─── Account health ───────────────────────────────────────────────────────

function AccountHealthTable({ rows, loading, error, onRetry, compact }) {
    const [filter, setFilter] = useState('all');
    const counts = { all: rows.length, action: rows.filter((row) => row.health.severity !== 'ok').length };
    counts.ok = counts.all - counts.action;
    const filtered = rows.filter((row) => filter === 'all' || (filter === 'action' ? row.health.severity !== 'ok' : row.health.severity === 'ok'));
    const visible = filtered.slice(0, compact ? 4 : 6);
    const maxOpen = Math.max(1, ...rows.map((row) => row.open ?? 0));
    return (
        <Card
            title="Account health"
            description={`Sorted by priority · ${formatCount(rows.length) || 0} accounts`}
            actions={rows.length > 0 ? (
                <SegmentedControl
                    label="Filter accounts"
                    value={filter}
                    onChange={setFilter}
                    options={[
                        { value: 'all', label: 'All', count: counts.all },
                        { value: 'action', label: 'Needs action', count: counts.action },
                        { value: 'ok', label: 'No alerts', count: counts.ok },
                    ]}
                />
            ) : null}
            footer={rows.length ? (
                <>
                    <span>Showing {visible.length} of {filtered.length}</span>
                    <Link className="nx-link" href="/dashboard/accounts">View all accounts →</Link>
                </>
            ) : null}
        >
            <DataState loading={loading} error={error} onRetry={onRetry} rows={5} empty={!loading && !error && filtered.length === 0} emptyTitle="No accounts match this view">
                <DataTable
                    label="Account health"
                    rows={visible}
                    getRowKey={(row) => row.tenantId}
                    columns={[
                        { key: 'account', header: 'Account', render: (row) => <Link href={`/dashboard/mps/${row.tenantId}`} className="nx-cc-account-link"><AccountIdentity name={row.name} detail={row.detail} /></Link> },
                        { key: 'status', header: 'Status', render: (row) => (
                            <span className="nx-cc-status">
                                <Badge tone={row.health.severity}>{row.health.severity === 'ok' ? 'No alerts' : SEVERITY_LABEL[row.health.severity]}</Badge>
                                {row.health.reasons[0] && <small>{row.health.reasons[0].detail || row.health.reasons[0].label}{row.health.reasons.length > 1 ? ` +${row.health.reasons.length - 1}` : ''}</small>}
                            </span>
                        ) },
                        { key: 'open', header: 'Open cases', render: (row) => (row.open === null ? <Unavailable /> : (
                            <span className="nx-cc-open"><strong>{formatCount(row.open)}</strong><ProgressBar value={row.open} max={maxOpen} tone={row.over14 ? 'warning' : 'forest-3'} label={`${row.open} open cases`} /></span>
                        )) },
                        { key: 'over14', header: '> 14 days', align: 'right', width: 80, hideBelow: 'sm', render: (row) => (row.over14 === null ? '—' : <span data-tone={row.over14 ? 'warning' : undefined} className="nx-cc-num">{formatCount(row.over14)}</span>) },
                        { key: 'last', header: 'Last case', align: 'right', hideBelow: 'xl', render: (row) => <span className="nx-muted">{row.lastCase || '—'}</span> },
                    ]}
                />
            </DataState>
        </Card>
    );
}

// ─── Platform health ──────────────────────────────────────────────────────

function PlatformHealth({ health, parliament, jobs, status }) {
    const whatsapp = health?.whatsapp;
    const freshness = parliament?.tenants ? parliamentFreshness(parliament.tenants) : null;
    const services = [
        {
            key: 'whatsapp', icon: MessageCircle, name: 'WhatsApp Cloud API',
            tone: whatsapp ? severityFromHealthStatus(whatsapp.status) : null,
            state: whatsapp ? ({ green: 'Operational', amber: 'Degraded', red: 'Down' }[whatsapp.status] || 'Unknown') : null,
            detail: whatsapp?.reason || null,
        },
        {
            key: 'webhook', icon: Webhook, name: 'Meta webhook',
            tone: whatsapp?.webhook ? severityFromHealthStatus(whatsapp.webhook.status) : null,
            state: whatsapp?.webhook ? (whatsapp.webhook.status === 'green' ? 'Receiving' : 'Needs review') : null,
            detail: whatsapp?.webhook?.last_webhook ? `Last event ${formatRelative(whatsapp.webhook.last_webhook)}` : whatsapp?.webhook?.detail || null,
        },
        {
            key: 'openai', icon: Bot, name: 'OpenAI (classification)',
            tone: health ? (health.openai?.configured ? 'ok' : 'critical') : null,
            state: health ? (health.openai?.configured ? 'Configured' : 'Not configured') : null,
            detail: 'Key configuration only — not a live check',
        },
        {
            key: 'gemini', icon: FileText, name: 'Gemini (drafting & OCR)',
            tone: health ? (health.gemini?.configured ? 'ok' : 'critical') : null,
            state: health ? (health.gemini?.configured ? 'Configured' : 'Not configured') : null,
            detail: 'Key configuration only — not a live check',
        },
        {
            key: 'parliament', icon: Landmark, name: 'Parliament sync',
            tone: freshness ? (freshness.statusCounts.needs_review ? 'review' : freshness.latestSync ? 'ok' : 'neutral') : null,
            state: freshness ? (freshness.statusCounts.needs_review ? `${freshness.statusCounts.needs_review} need review` : freshness.latestSync ? 'Synced' : 'Not synced yet') : null,
            detail: freshness ? (freshness.latestSync ? `Latest sync ${formatRelative(freshness.latestSync)} · ${freshness.accounts} accounts` : `${freshness.accounts} accounts enabled`) : null,
        },
        {
            key: 'jobs', icon: Workflow, name: 'Background jobs',
            tone: jobs?.summary ? (jobs.summary.failed ? 'warning' : 'ok') : null,
            state: jobs?.summary ? (jobs.summary.failed ? `${jobs.summary.failed} failed` : 'No failures') : null,
            detail: jobs?.summary ? `${jobs.summary.running} running · admin-triggered runs only` : null,
        },
    ];
    const known = services.filter((service) => service.tone);
    const healthy = known.filter((service) => service.tone === 'ok').length;
    const ordered = [...services].sort((a, b) => {
        const rank = (service) => (service.tone === 'critical' ? 0 : service.tone === 'warning' ? 1 : service.tone === 'review' ? 2 : service.tone === null ? 4 : 3);
        return rank(a) - rank(b);
    });
    return (
        <Card
            title="Platform health"
            description={known.length ? `${healthy} of ${known.length} signals healthy` : 'Checking services…'}
            actions={<Link className="nx-link" href="/dashboard/system/health">System →</Link>}
        >
            <ul className="nx-cc-services">
                {ordered.map((service) => {
                    const Icon = service.icon;
                    const loading = status.health === 'loading' && ['whatsapp', 'webhook', 'openai', 'gemini'].includes(service.key);
                    return (
                        <li key={service.key} data-tone={service.tone && service.tone !== 'ok' ? service.tone : undefined}>
                            <SeverityTile tone={service.tone && service.tone !== 'ok' ? service.tone : 'neutral'} icon={Icon} size="sm" />
                            <span className="nx-cc-service-copy">
                                <strong>{service.name}</strong>
                                {service.detail && <small>{service.detail}</small>}
                            </span>
                            {service.state
                                ? <StatusText tone={service.tone}>{service.state}</StatusText>
                                : <span className="nx-unavailable">{loading ? 'Checking…' : 'Unavailable'}</span>}
                        </li>
                    );
                })}
            </ul>
        </Card>
    );
}

// ─── Recent activity ──────────────────────────────────────────────────────

function humanizeAction(action) {
    const text = String(action || 'Admin action').replace(/[_.]+/g, ' ').trim();
    return text.charAt(0).toUpperCase() + text.slice(1);
}

function RecentActivity({ entries, loading, error, onRetry }) {
    return (
        <Card
            title="Recent activity"
            description="Administrator actions from the audit trail · last 7 days"
            actions={<Link className="nx-link" href="/dashboard/staff-access/audit">Audit log →</Link>}
        >
            <div className="nx-cc-pad">
                <DataState loading={loading} error={error} onRetry={onRetry} rows={2} empty={!loading && !error && entries.length === 0} emptyTitle="No administrator actions in the last 7 days">
                    <ol className="nx-cc-activity">
                        {entries.slice(0, 5).map((entry, index) => (
                            <li key={entry.id || `${entry.created_at}-${index}`}>
                                <Avatar size="sm" name={entry.admin_username || 'Administrator'} />
                                <div className="nx-cc-activity-copy">
                                    <span><strong>{entry.admin_username || 'Administrator'}</strong> {humanizeAction(entry.action).toLowerCase()}{entry.target_type ? ` · ${entry.target_type}${entry.target_id ? ` ${entry.target_id}` : ''}` : ''}</span>
                                    <small>{formatRelative(entry.created_at) || '—'}</small>
                                </div>
                            </li>
                        ))}
                    </ol>
                </DataState>
            </div>
        </Card>
    );
}

// ─── Page ─────────────────────────────────────────────────────────────────

export default function CommandCentre() {
    const { data, status, errors, load, loadAll } = useCommandCentreData();
    const signals = useAdminSignals();
    const compact = useMediaQuery('(max-width: 760px)');

    const accounts = useMemo(() => data.accounts?.mps || [], [data.accounts]);
    const accountLookup = useMemo(() => {
        const map = new Map();
        for (const account of accounts) {
            if (!map.has(String(account.tenant_id))) map.set(String(account.tenant_id), accountLabel(account));
        }
        return map;
    }, [accounts]);

    const whatsapp = data.health?.whatsapp || null;
    const alerts = status.alerts === 'ready' ? (data.alerts?.alerts || []) : null;
    const attention = useMemo(() => buildAttentionItems({ alerts, whatsapp, accounts: accountLookup }), [alerts, whatsapp, accountLookup]);
    const counts = attention ? countAttention(attention) : null;
    const { reportAttention } = signals;
    useEffect(() => {
        reportAttention?.(counts);
        return () => reportAttention?.(null);
    }, [counts?.critical, counts?.warning, counts?.total, reportAttention]); // eslint-disable-line react-hooks/exhaustive-deps

    const accountRows = useMemo(() => {
        if (status.accounts !== 'ready') return [];
        const incidents = deriveWhatsAppIncidents(whatsapp);
        const byTenant = data.cases?.open_by_tenant || null;
        const activity = new Map((data.activity?.tenants || []).map((tenant) => [String(tenant.tenant_id ?? tenant.id), tenant]));
        const seen = new Set();
        const rows = [];
        for (const account of accounts) {
            const id = String(account.tenant_id);
            if (seen.has(id)) continue;
            seen.add(id);
            const label = accountLookup.get(id);
            const caseEntry = byTenant ? (byTenant[id] || { open: 0, open_over_14_days: 0 }) : null;
            rows.push({
                tenantId: account.tenant_id,
                name: label.name,
                detail: label.detail,
                open: caseEntry ? caseEntry.open : null,
                over14: caseEntry ? caseEntry.open_over_14_days : null,
                lastCase: formatRelative(activity.get(id)?.last_case),
                health: accountHealth({ tenantId: id, alerts: alerts || [], whatsappIncidents: incidents }),
            });
        }
        const rank = { critical: 0, warning: 1, review: 2, notice: 3, ok: 4, neutral: 5 };
        return rows.sort((a, b) => (rank[a.health.severity] - rank[b.health.severity]) || ((b.open ?? -1) - (a.open ?? -1)) || a.name.localeCompare(b.name));
    }, [status.accounts, whatsapp, data.cases, data.activity, accounts, accountLookup, alerts]);

    const refresh = () => {
        loadAll();
        signals.refresh?.();
    };

    const updated = data.health?.last_checked ? formatRelative(data.health.last_checked) : null;
    const anyLoading = Object.values(status).some((value) => value === 'loading');

    return (
        <div className="nx-cc">
            <PageHeader
                title="Command Centre"
                description="Monitor accounts, cases and platform operations"
                meta={(
                    <span className="nx-cc-live">
                        <span className="nx-dot nx-dot-ring" data-tone={anyLoading ? 'neutral' : 'ok'} aria-hidden="true" />
                        {anyLoading ? 'Updating…' : updated ? `Health checked ${updated}` : 'Live'}
                    </span>
                )}
                actions={(
                    <>
                        <button type="button" className="nx-btn" onClick={refresh} disabled={anyLoading}>
                            <RefreshCw size={16} strokeWidth={1.9} aria-hidden="true" />Refresh
                        </button>
                        <Link href="/dashboard/accounts/new" className="nx-btn nx-btn-primary">
                            <Plus size={16} strokeWidth={2} aria-hidden="true" />Create account
                        </Link>
                    </>
                )}
            />

            <section className="nx-cc-summary" aria-label="Summary">
                <AttentionSummary counts={counts} ready={Boolean(counts)} error={status.alerts === 'error'} />
                <AccountsSummary stats={data.stats} accounts={accounts} whatsapp={whatsapp} statsReady={status.stats === 'ready'} accountsReady={status.accounts === 'ready'} />
                <CasesSummary stats={data.stats} cases={data.cases} statsReady={status.stats === 'ready'} casesReady={status.cases === 'ready'} />
            </section>

            <div className="nx-split-grid">
                <NeedsAttention items={attention} loading={status.alerts === 'loading'} error={errors.alerts} onRetry={() => load('alerts')} compact={compact} />
                <OperationalPulse inbound={data.inbound} health={data.health} jobs={data.jobs} status={status} />
            </div>

            <MobileDisclosure compact={compact} title="Case analytics" hint={data.cases ? `${formatCount(data.cases.open_now)} open · intake, resolution and ageing` : 'Intake, resolution and ageing'}>
                <div className="nx-split-grid nx-cc-analytics" data-align="stretch">
                    <CaseFlow cases={data.cases} loading={status.cases === 'loading'} error={errors.cases} onRetry={() => load('cases')} />
                    <CaseAgeing cases={data.cases} loading={status.cases === 'loading'} error={errors.cases} onRetry={() => load('cases')} />
                </div>
            </MobileDisclosure>

            <div className="nx-split-grid">
                <AccountHealthTable rows={accountRows} loading={status.accounts === 'loading'} error={errors.accounts} onRetry={() => load('accounts')} compact={compact} />
                <MobileDisclosure compact={compact} title="Platform health" hint="WhatsApp, AI providers, Parliament sync and jobs">
                    <PlatformHealth health={data.health} parliament={data.parliament} jobs={data.jobs} status={status} />
                </MobileDisclosure>
            </div>

            <MobileDisclosure compact={compact} title="Recent activity" hint="Administrator actions · last 7 days">
                <RecentActivity entries={data.audit?.entries || []} loading={status.audit === 'loading'} error={errors.audit} onRetry={() => load('audit')} />
            </MobileDisclosure>

            {compact && (
                <nav className="nx-cc-quick" aria-label="Quick links">
                    <Link href="/dashboard/cases-intelligence/explorer" className="nx-btn"><Briefcase size={16} aria-hidden="true" />Find a case</Link>
                    <Link href="/dashboard/system/whatsapp" className="nx-btn"><MessageCircle size={16} aria-hidden="true" />Messaging</Link>
                </nav>
            )}
        </div>
    );
}
