'use client';

import { useState } from 'react';
import Link from 'next/link';
import { gen2, gen2Fonts } from '@/lib/briefcase-tokens';
import OverviewMetricsStrip from '@/components/dashboard/OverviewMetricsStrip';
import GovtTrackingCard from '@/components/dashboard/GovtTrackingCard';
import IssuePressureCard from '@/components/dashboard/IssuePressureCard';
import OfficeTodoCard from '@/components/dashboard/OfficeTodoCard';

// Locked Overview design — approved visual baseline. Do not redesign.
// Data comes from GET /api/dashboard/overview (+ /api/dashboard/engagements,
// /api/dashboard/overview/local-signals) via lib/dashboard-mappers → mapOverviewResponse.
// Issue Pressure, Office To-do and Government Tracking load their own endpoints.

// Canonical Gen 2 tokens, with this view's own shades kept verbatim. The
// Overview is an approved locked baseline, so the five values that differ
// from canonical are preserved exactly rather than snapped to it — folding
// them in would be a (small) redesign of a locked surface. Resolve under a
// deliberate visual review, not here.
const C = {
    ...gen2,
    border: gen2.hair,
    borderStrong: gen2.hairStrong,
    red: gen2.err,
    muted: '#5F584B',      // canonical #6C6858
    faint: '#837A69',      // canonical #8A8270
    rustSoft: '#F0DED0',   // canonical #F1DED0
    amberSoft: '#F1E5CF',  // canonical #F2E6CF
    redSoft: '#F1D8D2',    // no canonical equivalent
    blue: '#45667C',       // Overview-only; not a status colour
    blueSoft: '#E2E8EA',
};

const SANS = gen2Fonts.sans;
const SERIF = gen2Fonts.serif;
const MONO = gen2Fonts.mono;

function ToneDot({ tone = 'green' }) {
    const color = tone === 'red' ? C.red : tone === 'rust' ? C.rust : tone === 'amber' ? C.amber : C.green;
    return <span className="op-dot" style={{ background: color }} />;
}

function getStateTone(state) {
    const key = String(state || '').toLowerCase();
    if (key.includes('needs') || key.includes('sync')) return 'attention';
    if (key.includes('ready') || key.includes('registered')) return 'positive';
    if (key.includes('department') || key.includes('govt update')) return 'government';
    if (key.includes('draft') || key.includes('unassigned')) return 'workflow';
    return 'neutral';
}

function Section({ title, action, children, className = '' }) {
    return (
        <section className={`op-panel ${className}`}>
            <div className="op-section-head">
                <h2>{title}</h2>
                {action ? <Link href={action.href}>{action.label}</Link> : null}
            </div>
            {children}
        </section>
    );
}

function AttentionQueue({ rows, onOpenCase, onRunAction }) {
    return (
        <Section
            title="Attention Queue"
            action={{ href: '/dashboard/sansadx', label: 'View full Briefcase ->' }}
            className="queue-panel"
        >
            <div className="queue-table" role="table" aria-label="Attention queue">
                <div className="queue-header" role="row">
                    <span>Case / Thread</span>
                    <span>Raw Message</span>
                    <span>Issue / Location</span>
                    <span>State</span>
                    <span>Next Action</span>
                </div>
                {rows.length === 0 ? (
                    <div className="queue-empty">Nothing needs attention right now.</div>
                ) : null}
                {rows.map((row) => (
                    <div
                        className="queue-row"
                        role="row"
                        key={row.id || row.caseId}
                        onClick={() => onOpenCase(row.caseId)}
                        onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                                event.preventDefault();
                                onOpenCase(row.caseId);
                            }
                        }}
                        tabIndex={0}
                    >
                        <div className="case-cell">
                            <div className="case-line">
                                <div className="case-id">
                                    {row.critical ? <span className="critical-mark" aria-label="Critical" /> : null}
                                    {row.id}
                                </div>
                                <div className={`state-cell state-${getStateTone(row.state)} mobile-state`}>
                                    <span>{row.state}</span>
                                </div>
                            </div>
                            <div className="case-meta">{row.meta}</div>
                        </div>
                        <p className="message-cell">{row.message}</p>
                        <div className="issue-cell">
                            <strong>{row.issue}</strong>
                            <span>{row.location}</span>
                        </div>
                        <div className={`state-cell state-${getStateTone(row.state)} desktop-state`}>
                            <span>{row.state}</span>
                        </div>
                        <div className="action-cell">
                            {row.action ? (
                                <button
                                    type="button"
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        onRunAction(row);
                                    }}
                                >
                                    {row.action.label}
                                </button>
                            ) : (
                                <span className="action-none">—</span>
                            )}
                        </div>
                    </div>
                ))}
            </div>
            <Link className="mobile-queue-footer" href="/dashboard/sansadx">{'View all cases ->'}</Link>
        </Section>
    );
}

const PRESENCE_LABEL = { strong: 'Strong', growing: 'Growing', thin: 'Thin', none: 'No presence' };
const PRESENCE_SHOWN = 6;

// Localities to show collapsed: the strongest, plus a couple with no contact yet
// (they are the point of a presence map).
export function presenceRows(localities, showAll) {
    if (showAll) return localities;
    const reached = localities.filter((l) => l.people > 0);
    const none = localities.filter((l) => l.people === 0);
    const keepNone = Math.min(2, none.length);
    return [...reached.slice(0, PRESENCE_SHOWN - keepNone), ...none.slice(0, PRESENCE_SHOWN - Math.min(reached.length, PRESENCE_SHOWN - keepNone))];
}

function PresenceMap({ presence }) {
    const [showAll, setShowAll] = useState(false);
    const { localities, withPresence, total, gazetteerKnown } = presence;
    const rows = presenceRows(localities, showAll);
    const max = Math.max(1, ...localities.map((l) => l.people));
    return (
        <Section title="Presence Map">
            <div className="presence-card">
                {localities.length === 0 ? (
                    <p className="presence-summary">No mapped localities yet.</p>
                ) : (
                    <p className="presence-summary">
                        <strong>{withPresence} of {total}</strong> localities are in touch with the office.
                        {!gazetteerKnown ? ' Add the constituency locality list to see places with no contact.' : ''}
                    </p>
                )}
                <div className="presence-list">
                    {rows.map((l) => (
                        <div className="presence-row" key={l.name}>
                            <span className="presence-name" title={l.name}>{l.name}</span>
                            <span className="presence-bar" aria-hidden="true">
                                <b className={`presence-fill ${l.status}`} style={{ width: `${(l.people / max) * 100}%` }} />
                            </span>
                            <strong title={`${l.people} ${l.people === 1 ? 'person' : 'people'} in touch`}>{l.people}</strong>
                            <span className={`presence-chip ${l.status}`}>{PRESENCE_LABEL[l.status]}</span>
                        </div>
                    ))}
                </div>
                {localities.length > rows.length || showAll ? (
                    <button type="button" className="presence-more" aria-expanded={showAll} onClick={() => setShowAll(!showAll)}>
                        {showAll ? 'Show fewer' : `Show all ${localities.length} localities`}
                    </button>
                ) : null}
                <p className="presence-note">People in touch = distinct people who have raised a grievance from that locality.</p>
            </div>
        </Section>
    );
}

function TodayAgenda({ items }) {
    return (
        <Section title="Today" action={{ href: '/dashboard', label: 'Open schedule ->' }}>
            <div className="agenda-list">
                {items.length === 0 ? (
                    <div className="agenda-row"><span>—</span><p>No engagements scheduled today.</p></div>
                ) : null}
                {items.map((item, idx) => (
                    <div className="agenda-row" key={`${item.time}-${item.item}-${idx}`}>
                        <span>{item.time}</span>
                        <p>{item.item}</p>
                    </div>
                ))}
            </div>
        </Section>
    );
}

function RecentMovement({ items }) {
    return (
        <Section title="Recent Movement">
            <div className="movement-list">
                {items.length === 0 ? (
                    <div className="movement-row"><span>—</span><ToneDot tone="rust" /><p>No recent activity.</p></div>
                ) : null}
                {items.map((item) => {
                    const body = (
                        <>
                            <span>{item.time}</span>
                            <ToneDot tone={item.tone} />
                            <p>{item.item}</p>
                        </>
                    );
                    return item.href ? (
                        <Link className="movement-row" href={item.href} key={item.id}>{body}</Link>
                    ) : (
                        <div className="movement-row" key={item.id}>{body}</div>
                    );
                })}
            </div>
        </Section>
    );
}

export const SIGNALS_SHOWN = 6;

export function signalRows(items, showLow) {
    const list = Array.isArray(items) ? items : [];
    const relevant = list.filter((i) => i.relevance > 0);
    const low = list.filter((i) => !(i.relevance > 0));
    return { shown: (showLow ? [...relevant, ...low] : relevant).slice(0, showLow ? 8 : SIGNALS_SHOWN), hidden: showLow ? 0 : low.length };
}

function LocalSignals({ items, loaded }) {
    const [showLow, setShowLow] = useState(false);
    const { shown, hidden } = signalRows(items, showLow);
    return (
        <section className="media-strip" aria-label="Local Signals">
            <div className="op-section-head">
                <h2>Local Signals</h2>
            </div>
            <div className="signal-list">
                {!loaded ? <p className="signal-empty">Loading local news…</p> : null}
                {loaded && shown.length === 0 && !hidden ? <p className="signal-empty">No local coverage picked up yet.</p> : null}
                {shown.map((item) => (
                    <article key={`${item.source}-${item.title}`} className={`signal-row${item.relevance > 0 ? '' : ' low'}`}>
                        <span className="signal-src">{item.age ? `${item.source} · ${item.age}` : item.source}</span>
                        {item.href ? (
                            <a className="signal-title" href={item.href} target="_blank" rel="noreferrer noopener">{item.title}</a>
                        ) : (
                            <p className="signal-title">{item.title}</p>
                        )}
                        {item.localities.length || item.issue || item.linked ? (
                            <div className="signal-tags">
                                {item.localities.map((l) => <span key={l} className="signal-tag loc">{l}</span>)}
                                {item.issue ? <span className="signal-tag issue">{item.issue}</span> : null}
                                {item.linked ? <span className="signal-link">● {item.linked}</span> : null}
                            </div>
                        ) : null}
                    </article>
                ))}
            </div>
            {hidden ? (
                <p className="signal-hidden">
                    {hidden} less relevant {hidden === 1 ? 'story' : 'stories'} hidden (no local place or civic issue).{' '}
                    <button type="button" onClick={() => setShowLow(true)}>Show</button>
                </p>
            ) : null}
        </section>
    );
}

export default function OverviewDashboard({ data, onNavigate }) {
    const go = typeof onNavigate === 'function' ? onNavigate : () => {};
    const openCase = (caseId) => {
        if (caseId == null) {
            go('/dashboard/sansadx');
            return;
        }
        go(`/dashboard/sansadx?case_id=${caseId}`);
    };
    const runAction = (row) => {
        if (row.action && row.action.href) {
            go(row.action.href);
            return;
        }
        openCase(row.caseId);
    };

    return (
        <main className="overview-dashboard">
            <header className="overview-head">
                <div>
                    <p className="overview-kicker">Constituency operations</p>
                    <h1>Overview</h1>
                    <p className="overview-context">{data.seat} · {data.dateLabel}</p>
                </div>
            </header>

            <OverviewMetricsStrip onOpenCase={openCase} />

            {/* Desktop (>=1440): two independent vertical columns with their own
                flow/gap so each section starts as soon as the one above it ends.
                Below that the two wrappers flatten (display:contents) and the
                sections re-flow into the approved responsive stack (see the
                max-width:1439 media block). */}
            <div className="overview-columns">
                <div className="overview-col overview-col-left">
                    <AttentionQueue rows={data.queue} onOpenCase={openCase} onRunAction={runAction} />
                    <IssuePressureCard signals={data.mediaLoaded ? data.media : null} onNavigate={go} />
                    <OfficeTodoCard onNavigate={go} />
                </div>
                <div className="overview-col overview-col-right">
                    <GovtTrackingCard syncIssues={data.govt.syncIssues} issues={data.govt.issues} onOpenCase={openCase} />
                    <PresenceMap presence={data.presence} />
                    <TodayAgenda items={data.today} />
                    <RecentMovement items={data.movement} />
                </div>
            </div>

            <LocalSignals items={data.media} loaded={data.mediaLoaded} />

            <style>{`
                .overview-dashboard {
                    min-height: 100dvh;
                    background: ${C.bg};
                    color: ${C.ink};
                    font-family: ${SANS};
                    padding: 22px 34px 40px;
                }

                .overview-dashboard * {
                    box-sizing: border-box;
                }

                .overview-dashboard ::selection {
                    background: ${C.green};
                    color: ${C.surface};
                }

                .overview-head {
                    display: flex;
                    align-items: end;
                    justify-content: space-between;
                    gap: 24px;
                    margin-bottom: 13px;
                }

                .overview-kicker,
                .case-meta,
                .queue-header,
                .state-cell,
                .action-cell button,
                .action-cell .action-none,
                .mobile-queue-footer,
                .movement-row span,
                .agenda-row span {
                    font-family: ${MONO};
                }

                .overview-kicker {
                    margin: 0 0 6px;
                    color: ${C.greenDeep};
                    font-size: 10px;
                    letter-spacing: 0.1em;
                    text-transform: uppercase;
                }

                .overview-dashboard h1 {
                    margin: 0;
                    font-family: ${SERIF};
                    font-size: clamp(32px, 3.4vw, 51px);
                    font-weight: 700;
                    letter-spacing: -0.035em;
                    line-height: 0.96;
                    color: ${C.ink};
                }

                .overview-context {
                    margin: 7px 0 0;
                    color: ${C.muted};
                    font-size: 13.5px;
                }

                .op-dot {
                    width: 7px;
                    height: 7px;
                    display: inline-block;
                    border-radius: 999px;
                }

                .overview-columns {
                    display: grid;
                    grid-template-columns: minmax(0, 1.68fr) minmax(324px, 0.92fr);
                    gap: 14px;
                    align-items: start;
                }

                .overview-col {
                    display: grid;
                    gap: 14px;
                    align-content: start;
                    min-width: 0;
                }

                .op-panel,
                .media-strip {
                    background: ${C.surface};
                    border: 1px solid ${C.border};
                }

                .op-section-head {
                    min-height: 48px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 16px;
                    padding: 12px 16px;
                    border-bottom: 1px solid ${C.border};
                }

                .op-section-head h2 {
                    margin: 0;
                    font-family: ${SERIF};
                    font-size: 21px;
                    font-weight: 670;
                    letter-spacing: -0.025em;
                    line-height: 1;
                    color: ${C.ink};
                }

                .op-section-head a {
                    color: ${C.greenDeep};
                    font-size: 11.5px;
                    text-decoration: none;
                    white-space: nowrap;
                    transition: color 150ms cubic-bezier(0.23, 1, 0.32, 1), transform 150ms cubic-bezier(0.23, 1, 0.32, 1);
                }

                @media (hover: hover) and (pointer: fine) {
                    .op-section-head a:hover {
                        color: ${C.rust};
                        transform: translateX(1px);
                    }
                }

                .op-section-head a:active,
                .action-cell button:active,
                .mobile-queue-footer:active {
                    transform: scale(0.98);
                }

                .queue-table {
                    width: 100%;
                }

                .queue-empty,
                .queue-header,
                .queue-row {
                    display: grid;
                    grid-template-columns: minmax(88px, 0.6fr) minmax(250px, 2.15fr) minmax(112px, 0.84fr) minmax(88px, 0.62fr) minmax(112px, 0.84fr);
                    column-gap: 9px;
                    align-items: center;
                }

                .queue-empty {
                    display: block;
                    padding: 16px 16px;
                    color: ${C.muted};
                    font-size: 13px;
                }

                .queue-header {
                    padding: 8px 16px;
                    color: ${C.faint};
                    font-size: 9.5px;
                    letter-spacing: 0.08em;
                    text-transform: uppercase;
                    border-bottom: 1px solid ${C.border};
                }

                .queue-row {
                    min-height: 78px;
                    padding: 11px 16px;
                    border-bottom: 1px solid ${C.border};
                    cursor: pointer;
                    transition: background 140ms cubic-bezier(0.23, 1, 0.32, 1);
                }

                .queue-row:last-child {
                    border-bottom: 0;
                }

                @media (hover: hover) and (pointer: fine) {
                    .queue-row:hover {
                        background: ${C.surfaceWarm};
                    }
                }

                .queue-row:focus-visible {
                    outline: 2px solid ${C.greenDeep};
                    outline-offset: -2px;
                }

                .case-line {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 10px;
                }

                .case-id {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-family: ${MONO};
                    font-size: 12px;
                    font-weight: 600;
                    color: ${C.ink};
                }

                .critical-mark {
                    width: 5px;
                    height: 20px;
                    background: ${C.red};
                    display: inline-block;
                }

                .case-meta {
                    margin-top: 4px;
                    color: ${C.faint};
                    font-size: 10px;
                    line-height: 1.2;
                }

                .message-cell {
                    margin: 0;
                    color: #1F1D17;
                    font-size: 13px;
                    font-weight: 620;
                    line-height: 1.3;
                    letter-spacing: -0.01em;
                    display: -webkit-box;
                    -webkit-line-clamp: 2;
                    -webkit-box-orient: vertical;
                    overflow: hidden;
                }

                .issue-cell {
                    display: grid;
                    gap: 3px;
                    font-size: 12px;
                    line-height: 1.2;
                }

                .issue-cell strong {
                    color: #2E2A22;
                    font-weight: 650;
                }

                .issue-cell span,
                .agenda-row p,
                .movement-row p {
                    color: ${C.muted};
                }

                .mobile-state {
                    display: none;
                }

                .state-cell span {
                    display: inline-flex;
                    width: fit-content;
                    max-width: 100%;
                    border: 1px solid ${C.borderStrong};
                    background: ${C.surfaceWarm};
                    padding: 4px 6px;
                    color: ${C.greenDeep};
                    font-size: 10px;
                    font-weight: 650;
                    letter-spacing: 0.04em;
                    text-transform: uppercase;
                    line-height: 1.1;
                    overflow-wrap: anywhere;
                }

                .state-attention span {
                    border-color: rgba(188, 106, 54, 0.42);
                    background: ${C.amberSoft};
                    color: #684010;
                }

                .state-positive span {
                    border-color: rgba(43, 110, 76, 0.34);
                    background: ${C.greenSoft};
                    color: ${C.greenDeep};
                }

                .state-workflow span {
                    border-color: rgba(69, 102, 124, 0.32);
                    background: ${C.blueSoft};
                    color: #2B4E63;
                }

                .state-government span {
                    border-color: rgba(43, 110, 76, 0.3);
                    background: #E9E8DA;
                    color: ${C.greenDeep};
                }

                .state-neutral span {
                    border-color: ${C.borderStrong};
                    background: ${C.neutralSoft};
                    color: ${C.muted};
                }

                .action-cell button {
                    display: inline-flex;
                    align-items: center;
                    max-width: 100%;
                    min-height: 26px;
                    border: 1px solid rgba(43, 110, 76, 0.34);
                    background: ${C.surface};
                    color: ${C.greenDeep};
                    cursor: pointer;
                    font-size: 10px;
                    font-weight: 650;
                    letter-spacing: 0.025em;
                    line-height: 1.15;
                    padding: 5px 7px;
                    text-align: left;
                    transition: border-color 150ms cubic-bezier(0.23, 1, 0.32, 1), background 150ms cubic-bezier(0.23, 1, 0.32, 1), color 150ms cubic-bezier(0.23, 1, 0.32, 1), transform 120ms cubic-bezier(0.23, 1, 0.32, 1);
                }

                .action-cell .action-none {
                    color: ${C.faint};
                    font-size: 11px;
                }

                @media (hover: hover) and (pointer: fine) {
                    .action-cell button:hover {
                        border-color: rgba(43, 110, 76, 0.42);
                        background: ${C.greenSoft};
                        color: ${C.greenDeep};
                    }
                }

                .mobile-queue-footer {
                    display: none;
                }

                .presence-card {
                    padding: 10px 16px 12px;
                }

                .presence-summary {
                    margin: 0 0 6px;
                    color: #514B3F;
                    font-size: 12px;
                }

                .presence-summary strong {
                    color: ${C.ink};
                }

                .presence-list {
                    display: grid;
                }

                .presence-row {
                    display: grid;
                    grid-template-columns: minmax(0, 1.4fr) minmax(40px, 1fr) 30px 86px;
                    gap: 10px;
                    align-items: center;
                    border-top: 1px solid ${C.border};
                    padding: 7px 0;
                    font-size: 12px;
                    color: #514B3F;
                }

                .presence-name {
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    color: ${C.ink};
                }

                .presence-bar {
                    height: 6px;
                    background: ${C.border};
                    border-radius: 3px;
                    overflow: hidden;
                }

                .presence-fill {
                    display: block;
                    height: 100%;
                    border-radius: 3px;
                    background: ${C.green};
                }

                .presence-fill.thin { background: ${C.amber}; }

                .presence-row strong {
                    font-family: ${MONO};
                    color: ${C.ink};
                    font-size: 12px;
                    text-align: right;
                }

                .presence-chip {
                    font-family: ${MONO};
                    font-size: 9.5px;
                    letter-spacing: .05em;
                    text-transform: uppercase;
                    padding: 2px 6px;
                    border-radius: 2px;
                    justify-self: end;
                    white-space: nowrap;
                }

                .presence-chip.strong { background: ${C.greenSoft}; color: ${C.green}; }
                .presence-chip.growing { background: ${C.blueSoft}; color: ${C.blue}; }
                .presence-chip.thin { background: ${C.amberSoft}; color: ${C.amber}; }
                .presence-chip.none { background: ${C.redSoft}; color: ${C.red}; }

                .presence-more {
                    margin-top: 8px;
                    border: 1px solid ${C.borderStrong};
                    background: transparent;
                    border-radius: 3px;
                    padding: 5px 10px;
                    font: 600 12px ${SANS};
                    color: ${C.green};
                    cursor: pointer;
                }

                .presence-note {
                    margin: 8px 0 0;
                    color: ${C.faint};
                    font-size: 11px;
                }

                .agenda-list,
                .movement-list {
                    display: grid;
                }

                .agenda-row:last-child,
                .movement-row:last-child {
                    border-bottom: 0;
                }

                .agenda-row,
                .movement-row {
                    display: grid;
                    align-items: center;
                    gap: 10px;
                    padding: 10px 16px;
                    border-bottom: 1px solid ${C.border};
                    text-decoration: none;
                }

                .agenda-row {
                    grid-template-columns: 46px 1fr;
                }

                .movement-row {
                    grid-template-columns: 42px auto 1fr;
                }

                @media (hover: hover) and (pointer: fine) {
                    a.movement-row:hover {
                        background: ${C.surfaceWarm};
                    }
                }

                .agenda-row span,
                .movement-row span {
                    color: ${C.faint};
                    font-size: 10px;
                }

                .agenda-row p,
                .movement-row p {
                    margin: 0;
                    color: ${C.ink};
                    font-size: 12px;
                    line-height: 1.3;
                }

                .media-strip {
                    margin-top: 14px;
                }

                .signal-list {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }

                .signal-row {
                    padding: 12px 16px;
                    border-bottom: 1px solid ${C.border};
                    min-width: 0;
                }

                .signal-row:nth-child(odd) {
                    border-right: 1px solid ${C.border};
                }

                .signal-row.low {
                    opacity: 0.75;
                }

                .signal-src {
                    display: block;
                    color: ${C.muted};
                    font-family: ${MONO};
                    font-size: 10px;
                    letter-spacing: 0.08em;
                    text-transform: uppercase;
                }

                .signal-title {
                    display: block;
                    margin: 3px 0 6px;
                    color: ${C.ink};
                    font-size: 13.5px;
                    font-weight: 600;
                    line-height: 1.35;
                    text-decoration: none;
                }

                a.signal-title:hover {
                    text-decoration: underline;
                }

                .signal-tags {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 6px;
                    align-items: center;
                }

                .signal-tag {
                    font-size: 11px;
                    padding: 1px 7px;
                    border-radius: 999px;
                    border: 1px solid ${C.border};
                    color: ${C.ink};
                }

                .signal-tag.loc {
                    background: ${C.blueSoft};
                    border-color: #C8D3DF;
                    color: ${C.blue};
                }

                .signal-tag.issue {
                    background: ${C.amberSoft};
                    border-color: #E5CF9F;
                    color: #8A5D12;
                }

                .signal-link {
                    font-size: 12px;
                    color: ${C.red};
                    font-weight: 600;
                }

                .signal-empty,
                .signal-hidden {
                    margin: 0;
                    padding: 12px 16px;
                    color: ${C.muted};
                    font-size: 12px;
                }

                .signal-hidden {
                    border-top: 1px solid ${C.border};
                }

                .signal-hidden button {
                    border: 0;
                    background: none;
                    padding: 0;
                    color: ${C.greenDeep};
                    font: inherit;
                    font-weight: 600;
                    cursor: pointer;
                }

                /* Below ~1440 the fixed 220px app rail leaves too little room for
                   the intended ~65/35 two-column composition, so fall back to the
                   approved responsive stack: Attention Queue full width, then
                   Government Tracking + Presence Map paired where space
                   allows, then every other section full width, all in the
                   approved order. The two column wrappers are flattened with
                   display:contents so order can interleave their children;
                   explicit flex-basis keeps every card using the full workspace
                   width (no narrow partial-width cards). */
                @media (max-width: 1439px) {
                    .overview-dashboard {
                        padding: 20px 24px 36px;
                    }

                    .overview-columns {
                        display: flex;
                        flex-wrap: wrap;
                        align-items: flex-start;
                        gap: 14px;
                    }

                    .overview-col {
                        display: contents;
                    }

                    .overview-col-left > :nth-child(1) { order: 1; flex: 1 1 100%; }                       /* Attention Queue */
                    .overview-col-right > :nth-child(1) { order: 2; flex: 1 1 calc(50% - 7px); min-width: 0; }  /* Government Tracking */
                    .overview-col-right > :nth-child(2) { order: 3; flex: 1 1 calc(50% - 7px); min-width: 0; }  /* Presence Map */
                    .overview-col-left > :nth-child(2) { order: 4; flex: 1 1 100%; }                       /* Issue Pressure */
                    .overview-col-right > :nth-child(3) { order: 5; flex: 1 1 100%; }                      /* Today */
                    .overview-col-left > :nth-child(3) { order: 6; flex: 1 1 100%; }                       /* Office To-do */
                    .overview-col-right > :nth-child(4) { order: 7; flex: 1 1 100%; }                      /* Recent Movement */

                    .queue-empty,
                    .queue-header,
                    .queue-row {
                        grid-template-columns: minmax(116px, 0.68fr) minmax(300px, 2.2fr) minmax(140px, 0.88fr) minmax(116px, 0.72fr) minmax(130px, 0.78fr);
                    }
                }

                @media (max-width: 1100px) {
                    .queue-empty,
                    .queue-header,
                    .queue-row {
                        grid-template-columns: minmax(78px, 0.58fr) minmax(230px, 2.05fr) minmax(104px, 0.82fr) minmax(82px, 0.62fr) minmax(96px, 0.72fr);
                        column-gap: 8px;
                    }

                    .queue-header {
                        padding-left: 14px;
                        padding-right: 14px;
                    }

                    .queue-row {
                        padding-left: 14px;
                        padding-right: 14px;
                    }

                    .message-cell {
                        font-size: 12.5px;
                    }

                    .action-cell button {
                        font-size: 9px;
                        padding-left: 6px;
                        padding-right: 6px;
                    }
                }

                @media (max-width: 1023px) {
                    .overview-head {
                        align-items: start;
                    }

                    /* Not enough width to pair them — Government Tracking and
                       Presence Map go full width, keeping the stack. */
                    .overview-col-right > :nth-child(1),
                    .overview-col-right > :nth-child(2) {
                        flex-basis: 100%;
                    }

                    .queue-header {
                        display: none;
                    }

                    .queue-row {
                        grid-template-columns: minmax(96px, 0.54fr) minmax(0, 1.46fr) minmax(118px, 0.62fr);
                        row-gap: 9px;
                        align-items: start;
                    }

                    .issue-cell,
                    .state-cell {
                        grid-column: 2;
                    }

                    .action-cell {
                        grid-column: 3;
                        grid-row: 1 / span 3;
                    }

                    .issue-cell {
                        display: flex;
                        gap: 8px;
                        flex-wrap: wrap;
                    }

                    .state-cell span {
                        white-space: normal;
                    }

                }

                @media (max-width: 640px) {
                    .overview-dashboard {
                        padding: 20px 14px 34px;
                    }

                    .overview-head {
                        display: grid;
                        gap: 14px;
                    }

                    .op-section-head {
                        padding: 12px 14px;
                    }

                    .op-section-head h2 {
                        font-size: 20px;
                    }

                    .queue-row {
                        grid-template-columns: 1fr;
                        min-height: 0;
                        padding: 13px 14px;
                        row-gap: 9px;
                    }

                    .queue-table .queue-row:nth-of-type(n + 6) {
                        display: none;
                    }

                    .message-cell,
                    .issue-cell,
                    .desktop-state,
                    .action-cell {
                        grid-column: auto;
                        grid-row: auto;
                    }

                    .desktop-state {
                        display: none;
                    }

                    .mobile-state {
                        display: inline-flex;
                    }

                    .issue-cell {
                        display: grid;
                    }

                    .case-cell {
                        display: flex;
                        justify-content: space-between;
                        gap: 12px;
                    }

                    .case-meta {
                        margin-top: 5px;
                        text-align: right;
                    }

                    .message-cell {
                        font-size: 12.75px;
                        margin-bottom: 5px;
                        -webkit-line-clamp: 3;
                    }

                    .action-cell button {
                        min-height: 28px;
                        padding: 0;
                        border: 0;
                        background: transparent;
                        color: ${C.greenDeep};
                        font-size: 11px;
                    }

                    .action-cell button::after {
                        content: ' ->';
                    }

                    .mobile-queue-footer {
                        display: block;
                        padding: 12px 14px 14px;
                        border-top: 1px solid ${C.border};
                        color: ${C.greenDeep};
                        font-size: 11px;
                        letter-spacing: 0.04em;
                        text-decoration: none;
                        text-transform: uppercase;
                        transition: color 150ms cubic-bezier(0.23, 1, 0.32, 1), transform 120ms cubic-bezier(0.23, 1, 0.32, 1);
                    }

                    .presence-card {
                        padding-left: 14px;
                        padding-right: 14px;
                    }

                    .signal-list {
                        grid-template-columns: 1fr;
                    }

                    .signal-row:nth-child(odd) {
                        border-right: 0;
                    }
                }
            `}</style>
        </main>
    );
}
