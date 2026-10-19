'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import {
    ArrowRight, Building2, CalendarDays, ChevronRight, Eye, FileText, Landmark, MapPin, RefreshCw,
} from 'lucide-react';
import { gen2, gen2Fonts, gen2Type } from '@/lib/briefcase-tokens';

// Operations Dashboard — Overview (design.md, "constituency command centre").
// Every figure comes from GET /api/dashboard/overview (+ /api/dashboard/engagements,
// /api/news?news_type=local) via lib/dashboard-mappers → mapOverviewResponse.
// Nothing here is illustrative: sections whose data is not recorded yet
// (department response times, overdue/awaiting-response stages, date ranges,
// trends, seat boundaries) render an honest note instead of a number.

const C = {
    ...gen2,
    border: gen2.hair,
    red: gen2.err,
    redSoft: '#F6E2DE',
    blue: '#295F91',      // information / registration (design.md token)
    blueSoft: '#E6EEF6',
};
const SANS = gen2Fonts.sans;
const SERIF = gen2Fonts.serif;
const MONO = gen2Fonts.mono;
const T = gen2Type;

const BUCKETS = [
    { key: 'needs_review', label: 'Needs review' },
    { key: 'needs_location', label: 'Needs location' },
    { key: 'sync_issues', label: 'Sync issues' },
    { key: 'govt_updates', label: 'Govt updates' },
    // The backend's `ready_to_file` attention bucket is every active thread that
    // is not yet filed with government — broader than the "Ready to file" KPI,
    // which is the portal-prepared stage. Labelled so the two never read as one.
    { key: 'ready_to_file', label: 'Not yet filed' },
];

function stateTone(state) {
    const key = String(state || '').toLowerCase();
    if (key.includes('needs review') || key.includes('sync')) return 'red';
    if (key.includes('needs location')) return 'amber';
    if (key.includes('ready')) return 'green';
    if (key.includes('registered') || key.includes('department') || key.includes('govt')) return 'blue';
    return 'neutral';
}

function formatReceived(value) {
    if (!value) return null;
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return null;
    return {
        date: d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }),
        time: d.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' }),
    };
}

function Panel({ id, title, action, note, className = '', children }) {
    return (
        <section id={id} className={`ov-panel ${className}`} aria-labelledby={id ? `${id}-title` : undefined}>
            <div className="ov-panel-head">
                <h2 id={id ? `${id}-title` : undefined}>{title}</h2>
                {action ? (
                    <Link href={action.href} className="ov-link">
                        {action.label} <ArrowRight size={14} aria-hidden="true" />
                    </Link>
                ) : null}
            </div>
            {children}
            {note ? <p className="ov-note">{note}</p> : null}
        </section>
    );
}

// ─── KPI strip ─────────────────────────────────────────────────────────
function KpiCard({ icon: Icon, tone, value, label, context, emphasis, href, onClick, title }) {
    const body = (
        <>
            <span className={`ov-kpi-icon tone-${tone}`} aria-hidden="true"><Icon size={24} strokeWidth={1.8} /></span>
            <span className="ov-kpi-text">
                <span className="ov-kpi-value">{Number(value || 0).toLocaleString('en-IN')}</span>
                <span className="ov-kpi-label">{label}</span>
                <span className="ov-kpi-context">{context}</span>
            </span>
            <ChevronRight className="ov-kpi-chev" size={18} aria-hidden="true" />
        </>
    );
    const cls = `ov-kpi${emphasis ? ' is-emphasis' : ''}`;
    if (href) return <Link className={cls} href={href} title={title}>{body}</Link>;
    return <button type="button" className={cls} onClick={onClick} title={title}>{body}</button>;
}

function KpiStrip({ data, onSelectBucket }) {
    const a = data.attentionByKey || {};
    const notFiled = a.ready_to_file || 0;
    const sync = a.sync_issues || 0;
    const updates = a.govt_updates || 0;
    return (
        <div className="ov-kpis" aria-label="Key counts">
            <KpiCard
                emphasis
                icon={FileText}
                tone="green"
                value={data.govt.ready}
                label="Ready to file"
                context={`Prepared for portal · ${notFiled.toLocaleString('en-IN')} active not yet filed`}
                href="#government-tracking"
                title="Threads whose government submission is prepared and waiting for staff to file on the portal"
            />
            <KpiCard
                icon={Eye}
                tone="amber"
                value={a.needs_review}
                label="Needs review"
                context="Awaiting staff review"
                href="/dashboard/sansadx?status=pending_review"
            />
            <KpiCard
                icon={MapPin}
                tone="red"
                value={a.needs_location}
                label="Needs location"
                context="Location not yet resolved"
                href="/dashboard/sansadx?status=awaiting_location"
            />
            <KpiCard
                icon={RefreshCw}
                tone="blue"
                value={sync}
                label="Sync issues"
                context={sync ? 'Latest portal check failed' : 'No pending issues'}
                onClick={() => onSelectBucket('sync_issues')}
            />
            <KpiCard
                icon={Landmark}
                tone="neutral"
                value={updates}
                label="Govt updates"
                context={updates ? 'New portal status to review' : 'No new updates'}
                onClick={() => onSelectBucket('govt_updates')}
            />
        </div>
    );
}

// ─── Attention Queue ───────────────────────────────────────────────────
function AttentionQueue({ rows, counts, tab, onTab, onOpenCase, onRunAction }) {
    const visible = tab === 'all' ? rows : rows.filter((row) => row.bucket === tab);
    const total = tab === 'all' ? null : (counts[tab] || 0);
    const tabs = [{ key: 'all', label: 'Latest', count: rows.length }, ...BUCKETS.map((b) => ({ ...b, count: counts[b.key] || 0 }))];

    return (
        <Panel id="attention-queue" title="Attention Queue" action={{ href: '/dashboard/sansadx', label: 'View all Briefcase' }} className="ov-queue">
            <div className="ov-tabs" role="tablist" aria-label="Attention queue filter">
                {tabs.map((t) => (
                    <button
                        key={t.key}
                        type="button"
                        role="tab"
                        aria-selected={tab === t.key}
                        className={tab === t.key ? 'is-active' : ''}
                        onClick={() => onTab(t.key)}
                    >
                        {t.label} <span>({t.count.toLocaleString('en-IN')})</span>
                    </button>
                ))}
            </div>

            <div className="ov-table" role="table" aria-label="Attention queue">
                <div className="ov-thead" role="row">
                    <span role="columnheader">Case</span>
                    <span role="columnheader">Grievance</span>
                    <span role="columnheader">Category</span>
                    <span role="columnheader">Location</span>
                    <span role="columnheader">State</span>
                    <span role="columnheader">Next action</span>
                    <span role="columnheader">Received</span>
                </div>
                {visible.length === 0 ? (
                    <div className="ov-empty">
                        {tab === 'all' ? 'Nothing needs attention right now.' : (total ? 'None of these are among the latest items — open Briefcase to see them.' : 'Nothing in this category.')}
                    </div>
                ) : null}
                {visible.map((row) => {
                    const received = formatReceived(row.receivedAt);
                    const tone = stateTone(row.state);
                    return (
                        <div
                            key={row.caseId ?? row.id}
                            role="row"
                            tabIndex={0}
                            className={`ov-row${row.critical ? ' is-critical' : ''}`}
                            aria-label={`Open case ${row.id}${row.critical ? ' (critical)' : ''}`}
                            onClick={() => onOpenCase(row.caseId)}
                            onKeyDown={(event) => {
                                if (event.key === 'Enter' || event.key === ' ') {
                                    event.preventDefault();
                                    onOpenCase(row.caseId);
                                }
                            }}
                        >
                            <div role="cell" className="ov-c-case">
                                <strong>{row.id}</strong>
                                <span>{row.threadCount > 1 ? `Thread · ${row.threadCount}` : '1 complaint'}</span>
                                {row.recency ? <span>{row.recency} ago</span> : null}
                            </div>
                            <p role="cell" className="ov-c-msg">{row.message || <em>No message text</em>}</p>
                            <div role="cell" className="ov-c-cat">{row.issue}</div>
                            <div role="cell" className="ov-c-loc">{row.location}</div>
                            <div role="cell" className="ov-c-state"><span className={`ov-badge tone-${tone}`}>{row.state}</span></div>
                            <div role="cell" className="ov-c-action">
                                {row.action ? (
                                    <button
                                        type="button"
                                        onClick={(event) => { event.stopPropagation(); onRunAction(row); }}
                                    >
                                        {row.action.label}
                                    </button>
                                ) : <span className="ov-dash">—</span>}
                            </div>
                            <div role="cell" className="ov-c-recv">
                                {received ? (<><span>{received.date}</span><span>{received.time}</span></>) : '—'}
                            </div>
                        </div>
                    );
                })}
            </div>
            <div className="ov-queue-foot">
                {tab === 'all'
                    ? `Latest ${rows.length} items needing attention, newest citizen message first.`
                    : `Showing ${visible.length} of ${(total || 0).toLocaleString('en-IN')} (latest items only).`}
                <Link href="/dashboard/sansadx" className="ov-link">Open Briefcase <ArrowRight size={14} aria-hidden="true" /></Link>
            </div>
        </Panel>
    );
}

// ─── Government Tracking ───────────────────────────────────────────────
function GovernmentTracking({ govt }) {
    const stages = [
        { key: 'ready', label: 'Ready to file (prepared for portal)', value: govt.ready, tone: 'green' },
        { key: 'registered', label: 'Registered with portal', value: govt.registered, tone: 'blue' },
        { key: 'department', label: 'Department action', value: govt.department, tone: 'amber' },
        { key: 'resolved', label: 'Resolved by government', value: govt.resolved, tone: 'deep' },
    ];
    const max = Math.max(1, ...stages.map((s) => s.value || 0));
    return (
        <Panel
            id="government-tracking"
            title="Government Tracking"
            action={{ href: '/dashboard/sansadx', label: 'Open Briefcase' }}
            note="Threads by current government stage — each counted once, all time. Awaiting-response and overdue stages need government response dates, which are not recorded yet."
        >
            <ul className="ov-bars">
                {stages.map((s) => (
                    <li key={s.key}>
                        <span className={`ov-bar-key tone-${s.tone}`} aria-hidden="true" />
                        <span className="ov-bar-label">{s.label}</span>
                        <span className="ov-bar-track" aria-hidden="true">
                            <span className={`ov-bar-fill tone-${s.tone}`} style={{ width: `${((s.value || 0) / max) * 100}%` }} />
                        </span>
                        <strong>{(s.value || 0).toLocaleString('en-IN')}</strong>
                    </li>
                ))}
            </ul>
            <div className={`ov-sync${govt.syncIssues ? ' has-issues' : ''}`}>
                <div>
                    <strong>{govt.syncIssues} sync {govt.syncIssues === 1 ? 'issue' : 'issues'}</strong>
                    <span>{govt.syncIssues ? 'Latest portal status check failed or needs verification.' : 'All portal status checks are current.'}</span>
                </div>
                {govt.issues.length ? (
                    <ul>{govt.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
                ) : null}
            </div>
        </Panel>
    );
}

// ─── Constituency Pressure (ranked hotspots — no fictional geography) ──
function ConstituencyPressure({ hotspots }) {
    const max = Math.max(1, ...hotspots.map((h) => h.count || 0));
    return (
        <Panel
            id="constituency-pressure"
            title="Constituency Pressure"
            note="Top locations by thread count, all time. A map will appear once verified boundaries are available for this seat."
        >
            {hotspots.length === 0 ? (
                <div className="ov-empty">No located grievances yet.</div>
            ) : (
                <ol className="ov-ranked">
                    {hotspots.map((h, i) => (
                        <li key={h.name}>
                            <Link href={`/dashboard/sansadx?location=${encodeURIComponent(h.name)}`}>
                                <span className="ov-rank">{i + 1}</span>
                                <span className="ov-ranked-name">{h.name}</span>
                                <span className="ov-bar-track" aria-hidden="true">
                                    <span className="ov-bar-fill tone-deep" style={{ width: `${((h.count || 0) / max) * 100}%` }} />
                                </span>
                                <strong>{h.count}</strong>
                            </Link>
                        </li>
                    ))}
                </ol>
            )}
        </Panel>
    );
}

// ─── Bottom row ────────────────────────────────────────────────────────
const ISSUE_TONES = ['sage', 'blue', 'amber', 'violet', 'rose'];

function TopIssues({ items }) {
    const max = Math.max(1, ...items.map((i) => i.count || 0));
    return (
        <Panel
            id="top-issues"
            title="Top Issues"
            action={{ href: '/dashboard/sansadx', label: 'Open Briefcase' }}
            note="Grievance threads by category, all time."
        >
            {items.length === 0 ? <div className="ov-empty">No categorised grievances yet.</div> : (
                <ul className="ov-issues">
                    {items.map((item, i) => (
                        <li key={item.title}>
                            <span className="ov-issue-name">
                                {item.title}
                                {item.place ? <small>{item.place}</small> : null}
                            </span>
                            <span className="ov-bar-track" aria-hidden="true">
                                <span className={`ov-bar-fill tone-${ISSUE_TONES[i % ISSUE_TONES.length]}`} style={{ width: `${((item.count || 0) / max) * 100}%` }} />
                            </span>
                            <strong>{item.count}</strong>
                        </li>
                    ))}
                </ul>
            )}
        </Panel>
    );
}

function DepartmentResponse() {
    return (
        <Panel id="department-response" title="Department Response Time">
            <div className="ov-placeholder">
                <Building2 size={26} strokeWidth={1.6} aria-hidden="true" />
                <p>Response-time analytics will appear once government filing and response timestamps are available.</p>
            </div>
        </Panel>
    );
}

function RecentActivity({ items }) {
    return (
        <Panel
            id="recent-activity"
            title="Recent Activity"
            action={{ href: '/dashboard/archives', label: 'View all' }}
            note="Office activity log (drafts, letters and other office actions)."
        >
            {items.length === 0 ? <div className="ov-empty">No recent activity.</div> : (
                <ol className="ov-activity">
                    {items.map((item) => {
                        const body = (
                            <>
                                <span className="ov-act-time">{item.time}</span>
                                <span className={`ov-act-dot tone-${item.tone === 'green' ? 'green' : 'amber'}`} aria-hidden="true" />
                                <span className="ov-act-text">{item.item}</span>
                            </>
                        );
                        return (
                            <li key={item.id}>
                                {item.href ? <Link href={item.href}>{body}</Link> : <div>{body}</div>}
                            </li>
                        );
                    })}
                </ol>
            )}
        </Panel>
    );
}

// ─── Office row (existing Overview features kept below the reference layout)
function TodayAgenda({ items }) {
    return (
        <Panel id="today" title="Today">
            {items.length === 0 ? <div className="ov-empty">No engagements scheduled today.</div> : (
                <ul className="ov-simple">
                    {items.map((item, idx) => (
                        <li key={`${item.time}-${item.item}-${idx}`}><span>{item.time || '—'}</span><p>{item.item}</p></li>
                    ))}
                </ul>
            )}
        </Panel>
    );
}

function OfficePending({ items, onNavigate }) {
    return (
        <Panel id="office-pending" title="Office Pending">
            <ul className="ov-pending">
                {items.map((item) => (
                    <li key={item.key || item.label}>
                        <button type="button" onClick={() => (item.href ? onNavigate(item.href) : undefined)}>
                            {item.label} <ChevronRight size={16} aria-hidden="true" />
                        </button>
                    </li>
                ))}
            </ul>
        </Panel>
    );
}

function LocalSignals({ items }) {
    return (
        <Panel id="local-signals" title="Local Signals">
            {items.length === 0 ? <div className="ov-empty">No local coverage picked up yet.</div> : (
                <ul className="ov-simple">
                    {items.map((item) => (
                        <li key={`${item.source}-${item.title}`}>
                            <span>{item.source}</span>
                            {item.href
                                ? <a href={item.href} target="_blank" rel="noreferrer noopener">{item.title}</a>
                                : <p>{item.title}</p>}
                        </li>
                    ))}
                </ul>
            )}
        </Panel>
    );
}

export default function OverviewDashboard({ data, onNavigate }) {
    const go = typeof onNavigate === 'function' ? onNavigate : () => {};
    const [tab, setTab] = useState('all');
    const counts = useMemo(() => data.attentionByKey || {}, [data.attentionByKey]);

    const openCase = (caseId) => go(caseId == null ? '/dashboard/sansadx' : `/dashboard/sansadx?case_id=${caseId}`);
    const runAction = (row) => (row.action && row.action.href ? go(row.action.href) : openCase(row.caseId));
    const selectBucket = (key) => {
        setTab(key);
        if (typeof document !== 'undefined') {
            document.getElementById('attention-queue')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    };

    return (
        <main className="ov">
            <header className="ov-head">
                <div>
                    <h1>Overview</h1>
                    <p>Grievance status, key insights and actions for today{data.seat ? ` · ${data.seat}` : ''}.</p>
                </div>
                <div className="ov-scope" title="Date filtering is not available yet — every figure covers all time.">
                    <CalendarDays size={16} aria-hidden="true" />
                    <span>All time</span>
                </div>
            </header>

            <KpiStrip data={data} onSelectBucket={selectBucket} />

            <div className="ov-main">
                <AttentionQueue
                    rows={data.queue}
                    counts={counts}
                    tab={tab}
                    onTab={setTab}
                    onOpenCase={openCase}
                    onRunAction={runAction}
                />
                <div className="ov-side">
                    <GovernmentTracking govt={data.govt} />
                    <ConstituencyPressure hotspots={data.hotspots} />
                </div>
            </div>

            <div className="ov-bottom">
                <TopIssues items={data.issuePressure} />
                <DepartmentResponse />
                <RecentActivity items={data.movement} />
            </div>

            <div className="ov-bottom ov-office">
                <TodayAgenda items={data.today} />
                <OfficePending items={data.officePending} onNavigate={go} />
                <LocalSignals items={data.media} />
            </div>

            <style>{`
                .ov { min-height: 100dvh; background: ${C.bg}; color: ${C.ink}; font-family: ${SANS}; padding: 22px 28px 40px; font-size: ${T.body}px; }
                .ov *, .ov *::before, .ov *::after { box-sizing: border-box; }
                .ov a { color: inherit; text-decoration: none; }
                .ov :focus-visible { outline: 2px solid ${C.greenDeep}; outline-offset: 2px; }

                .ov-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
                .ov-head h1 { margin: 0; font-family: ${SERIF}; font-weight: 700; font-size: clamp(34px, 3.2vw, 46px); letter-spacing: -0.02em; line-height: 1; }
                .ov-head p { margin: 8px 0 0; color: ${C.muted}; font-size: 15px; }
                .ov-scope { display: inline-flex; align-items: center; gap: 8px; padding: 9px 14px; background: ${C.surface}; border: 1px solid ${C.border}; border-radius: 6px; font-size: ${T.body}px; color: ${C.ink}; }

                .ov-kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
                .ov-kpi { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 14px; padding: 16px 16px; background: ${C.surface}; border: 1px solid ${C.border}; border-radius: 6px; text-align: left; font: inherit; color: inherit; cursor: pointer; transition: border-color 120ms ease, background-color 120ms ease; min-width: 0; }
                .ov-kpi:hover { border-color: ${C.hairStrong}; background: ${C.rowHover}; }
                .ov-kpi.is-emphasis { border-color: ${C.green}; background: ${C.greenSoft}; box-shadow: inset 0 0 0 1px ${C.green}; }
                .ov-kpi-icon { width: 52px; height: 52px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; }
                .ov-kpi-text { display: flex; flex-direction: column; min-width: 0; }
                .ov-kpi-value { font-family: ${SERIF}; font-weight: 700; font-size: 34px; line-height: 1; letter-spacing: -0.01em; }
                .ov-kpi-label { margin-top: 6px; font-size: 15px; font-weight: 500; }
                .ov-kpi-context { margin-top: 6px; font-size: ${T.small}px; color: ${C.muted}; line-height: 1.35; }
                .ov-kpi-chev { color: ${C.muted}; }

                .tone-green  { --tone: ${C.green};  --tone-soft: ${C.greenSoft}; }
                .tone-deep   { --tone: ${C.greenDeep}; --tone-soft: ${C.greenSoft}; }
                .tone-amber  { --tone: ${C.amber};  --tone-soft: ${C.amberSoft}; }
                .tone-red    { --tone: ${C.red};    --tone-soft: ${C.redSoft}; }
                .tone-blue   { --tone: ${C.blue};   --tone-soft: ${C.blueSoft}; }
                .tone-neutral{ --tone: ${C.muted};  --tone-soft: ${C.neutralSoft}; }
                .tone-sage   { --tone: #8FB5A0; } .tone-violet { --tone: #9C95C9; } .tone-rose { --tone: #D49189; }
                .ov-kpi-icon { background: var(--tone-soft); color: var(--tone); }
                .ov-kpi.is-emphasis .ov-kpi-icon { background: ${C.green}; color: ${C.surface}; }

                .ov-panel { background: ${C.surface}; border: 1px solid ${C.border}; border-radius: 6px; padding: 16px 18px; min-width: 0; display: flex; flex-direction: column; }
                .ov-panel-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
                .ov-panel-head h2 { margin: 0; font-family: ${SERIF}; font-weight: 700; font-size: 22px; letter-spacing: -0.01em; }
                .ov-link { display: inline-flex; align-items: center; gap: 4px; font-size: ${T.small}px; font-weight: 600; color: ${C.greenDeep} !important; white-space: nowrap; }
                .ov-link:hover { text-decoration: underline !important; }
                .ov-note { margin: 12px 0 0; padding-top: 10px; border-top: 1px solid ${C.hairSoft}; font-size: ${T.small}px; color: ${C.muted}; line-height: 1.45; }
                .ov-empty { padding: 18px 4px; color: ${C.muted}; font-size: ${T.body}px; }

                .ov-main { display: grid; grid-template-columns: minmax(0, 2.2fr) minmax(300px, 1fr); gap: 16px; margin-bottom: 16px; align-items: start; }
                .ov-side { display: flex; flex-direction: column; gap: 16px; min-width: 0; }

                .ov-tabs { display: flex; gap: 4px; border-bottom: 1px solid ${C.border}; margin: 0 -18px 0; padding: 0 12px; overflow-x: auto; }
                .ov-tabs button { border: 0; background: transparent; font: inherit; font-size: ${T.body}px; color: ${C.muted}; padding: 10px 8px; border-bottom: 2px solid transparent; margin-bottom: -1px; cursor: pointer; white-space: nowrap; }
                .ov-tabs button span { font-size: ${T.small}px; }
                .ov-tabs button.is-active { color: ${C.greenDeep}; font-weight: 600; border-bottom-color: ${C.green}; }

                .ov-table { margin: 0 -18px; overflow-x: auto; }
                .ov-thead, .ov-row { display: grid; grid-template-columns: minmax(84px, 0.75fr) minmax(160px, 2fr) minmax(90px, 1fr) minmax(96px, 1fr) minmax(100px, 0.95fr) minmax(116px, 1fr) minmax(70px, 0.7fr); gap: 10px; align-items: start; padding: 12px 18px; }
                .ov-thead { padding-top: 10px; padding-bottom: 10px; border-bottom: 1px solid ${C.border}; font-size: ${T.small}px; color: ${C.muted}; font-weight: 600; }
                .ov-row { border-bottom: 1px solid ${C.hairSoft}; cursor: pointer; box-shadow: inset 3px 0 0 transparent; transition: background-color 120ms ease; }
                .ov-row:hover { background: ${C.rowHover}; }
                .ov-row.is-critical { box-shadow: inset 3px 0 0 ${C.red}; }
                .ov-c-case strong { display: block; font-family: ${MONO}; font-size: ${T.caseId}px; }
                .ov-c-case span { display: block; margin-top: 2px; white-space: nowrap; font-family: ${MONO}; font-size: ${T.meta}px; color: ${C.muted}; }
                .ov-c-msg { margin: 0; font-size: ${T.body}px; line-height: 1.4; font-weight: 500; overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
                .ov-c-cat, .ov-c-loc { font-size: ${T.small}px; line-height: 1.35; overflow-wrap: anywhere; }
                .ov-c-loc { color: ${C.muted}; }
                .ov-badge { display: inline-block; padding: 4px 7px; font-family: ${MONO}; font-size: ${T.badge}px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; line-height: 1.25; border: 1px solid var(--tone); color: var(--tone); background: var(--tone-soft); }
                .ov-c-action button { font: inherit; font-size: ${T.control}px; font-weight: 600; color: ${C.greenDeep}; background: transparent; border: 1px solid ${C.hairStrong}; border-radius: 4px; padding: 7px 10px; cursor: pointer; white-space: nowrap; }
                .ov-c-action button:hover { border-color: ${C.green}; background: ${C.greenSoft}; }
                .ov-dash { color: ${C.faint}; }
                .ov-c-recv { display: flex; flex-direction: column; font-size: ${T.small}px; color: ${C.muted}; }
                .ov-queue-foot { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; padding-top: 12px; font-size: ${T.small}px; color: ${C.muted}; }

                .ov-bars, .ov-ranked, .ov-issues, .ov-activity, .ov-simple, .ov-pending { list-style: none; margin: 0; padding: 0; }
                .ov-bars li { display: grid; grid-template-columns: 4px minmax(0, 1fr) minmax(70px, 38%) 44px; align-items: center; gap: 10px; padding: 8px 0; font-size: ${T.body}px; }
                .ov-bar-key { width: 4px; height: 18px; background: var(--tone); }
                .ov-bar-label { min-width: 0; }
                .ov-bar-track { display: block; height: 14px; background: ${C.paper}; border-radius: 2px; overflow: hidden; }
                .ov-bar-fill { display: block; height: 100%; min-width: 2px; background: var(--tone); }
                .ov-bars strong, .ov-ranked strong, .ov-issues strong { text-align: right; font-size: 15px; font-variant-numeric: tabular-nums; }
                .ov-sync { margin-top: 10px; padding: 10px 12px; border: 1px solid ${C.border}; background: ${C.surfaceWarm}; font-size: ${T.small}px; }
                .ov-sync.has-issues { border-color: ${C.red}; background: ${C.redSoft}; }
                .ov-sync strong { display: block; font-size: ${T.body}px; }
                .ov-sync span { color: ${C.muted}; }
                .ov-sync ul { margin: 6px 0 0; padding-left: 18px; font-family: ${MONO}; font-size: ${T.meta}px; }

                .ov-ranked a { display: grid; grid-template-columns: 24px minmax(0, 1fr) minmax(60px, 35%) 40px; align-items: center; gap: 10px; padding: 8px 0; font-size: ${T.body}px; border-bottom: 1px solid ${C.hairSoft}; }
                .ov-ranked li:last-child a { border-bottom: 0; }
                .ov-ranked a:hover .ov-ranked-name { text-decoration: underline; }
                .ov-rank { width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; background: ${C.paper}; font-size: ${T.meta}px; font-family: ${MONO}; }

                .ov-bottom { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; align-items: start; }
                .ov-issues li { display: grid; grid-template-columns: minmax(0, 1fr) minmax(70px, 40%) 44px; align-items: center; gap: 12px; padding: 8px 0; font-size: ${T.body}px; }
                .ov-issue-name small { display: block; color: ${C.muted}; font-size: ${T.meta}px; margin-top: 2px; }
                .ov-placeholder { display: flex; flex-direction: column; align-items: flex-start; gap: 10px; padding: 14px; background: ${C.surfaceWarm}; border: 1px dashed ${C.hairStrong}; color: ${C.muted}; }
                .ov-placeholder p { margin: 0; font-size: ${T.body}px; line-height: 1.45; color: ${C.ink}; }
                .ov-activity li > a, .ov-activity li > div { display: grid; grid-template-columns: 74px 12px minmax(0, 1fr); align-items: start; gap: 10px; padding: 9px 0; border-bottom: 1px solid ${C.hairSoft}; font-size: ${T.body}px; }
                .ov-activity li:last-child > a, .ov-activity li:last-child > div { border-bottom: 0; }
                .ov-activity a:hover .ov-act-text { text-decoration: underline; }
                .ov-act-time { font-size: ${T.small}px; color: ${C.muted}; }
                .ov-act-dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 5px; background: var(--tone); }

                .ov-office .ov-panel-head h2 { font-size: 18px; }
                .ov-simple li { display: grid; grid-template-columns: 90px minmax(0, 1fr); gap: 10px; padding: 7px 0; border-bottom: 1px solid ${C.hairSoft}; font-size: ${T.body}px; }
                .ov-simple li:last-child { border-bottom: 0; }
                .ov-simple span { font-size: ${T.small}px; color: ${C.muted}; }
                .ov-simple p { margin: 0; }
                .ov-simple a:hover { text-decoration: underline; }
                .ov-pending button { width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 8px; font: inherit; font-size: ${T.body}px; text-align: left; background: transparent; border: 0; border-bottom: 1px solid ${C.hairSoft}; padding: 9px 0; cursor: pointer; color: ${C.ink}; }
                .ov-pending li:last-child button { border-bottom: 0; }
                .ov-pending button:hover { color: ${C.greenDeep}; }

                /* 1440 → 1280: KPIs stay in one row but tighten. */
                @media (max-width: 1499px) {
                    .ov-kpi { grid-template-columns: auto 1fr; gap: 12px; padding: 14px; }
                    .ov-kpi-chev { display: none; }
                    .ov-kpi-icon { width: 44px; height: 44px; }
                    .ov-kpi-value { font-size: 30px; }
                }
                /* Below 1500 the two-thirds column is too narrow for a 7-column
                   table: the queue takes the full width and the side panels pair up. */
                @media (max-width: 1499px) {
                    .ov-main { grid-template-columns: minmax(0, 1fr); }
                    .ov-side { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
                }
                @media (max-width: 1359px) {
                    .ov-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
                }
                @media (max-width: 1100px) {
                    .ov-bottom { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                    .ov-bottom > :last-child { grid-column: 1 / -1; }
                }
                /* Below ~1200 the content area (minus the 220px sidebar) can't hold
                   the 7-column table: queue rows become cards. */
                @media (max-width: 1199px) {
                    .ov-thead { display: none; }
                    .ov-table { overflow-x: visible; }
                    .ov-row { grid-template-columns: minmax(0, 1fr) auto; grid-template-areas: "case state" "msg msg" "cat cat" "loc loc" "action recv"; gap: 6px 12px; padding: 14px 18px; }
                    .ov-c-case { grid-area: case; } .ov-c-state { grid-area: state; } .ov-c-msg { grid-area: msg; }
                    .ov-c-cat { grid-area: cat; font-weight: 600; } .ov-c-loc { grid-area: loc; }
                    .ov-c-action { grid-area: action; margin-top: 6px; } .ov-c-recv { grid-area: recv; flex-direction: row; gap: 6px; align-self: end; }
                }
                /* Tablet and below: panels stack. */
                @media (max-width: 1023px) {
                    .ov { padding: 18px 16px 32px; }
                    .ov-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                    .ov-kpis > :first-child { grid-column: 1 / -1; }
                    .ov-side { grid-template-columns: minmax(0, 1fr); }
                }
                @media (max-width: 767px) {
                    .ov-bottom { grid-template-columns: minmax(0, 1fr); }
                    .ov-kpis { grid-template-columns: minmax(0, 1fr); }
                    .ov-head h1 { font-size: 34px; }
                }
            `}</style>
        </main>
    );
}
