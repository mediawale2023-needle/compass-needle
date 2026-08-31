'use client';

import Link from 'next/link';

// Locked Overview design — approved visual baseline. Do not redesign.
// Data comes from GET /api/dashboard/overview (+ /api/dashboard/engagements,
// /api/news?news_type=local) via lib/dashboard-mappers → mapOverviewResponse.

const C = {
    bg: '#F3EEE2',
    surface: '#FFFEFB',
    surfaceWarm: '#F8F1E0',
    paper: '#EEE5D2',
    border: '#E4DECB',
    borderStrong: '#C9BFA9',
    ink: '#211F19',
    muted: '#5F584B',
    faint: '#837A69',
    green: '#2B6E4C',
    greenDeep: '#245F45',
    greenSoft: '#E4EBDD',
    rust: '#BC6A36',
    rustSoft: '#F0DED0',
    red: '#A33A32',
    redSoft: '#F1D8D2',
    amber: '#C9821C',
    amberSoft: '#F1E5CF',
    blue: '#45667C',
    blueSoft: '#E2E8EA',
    neutralSoft: '#ECE6D8',
};

const SANS = '"Public Sans", "Noto Sans Devanagari", system-ui, sans-serif';
const SERIF = '"Source Serif 4", Georgia, serif';
const MONO = '"IBM Plex Mono", ui-monospace, SFMono-Regular, monospace';

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

function AttentionStrip({ items }) {
    return (
        <div className="attention-strip" aria-label="Attention counters">
            {items.map((item) => (
                <div className="attention-item" key={item.key || item.label}>
                    <ToneDot tone={item.tone} />
                    <span className="attention-value">{item.value}</span>
                    <span className="attention-label">{item.label}</span>
                </div>
            ))}
        </div>
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

function GovernmentTracking({ govt }) {
    const steps = [
        ['Ready to file', govt.ready],
        ['Registered with portal', govt.registered],
        ['Department Action', govt.department],
    ];

    return (
        <Section title="Government Tracking" action={{ href: '/dashboard/sansadx', label: 'Open government cases ->' }}>
            <div className="journey">
                {steps.map(([label, value], idx) => (
                    <div className="journey-step" key={label}>
                        <div>
                            <span>{label}</span>
                            <strong>{value}</strong>
                        </div>
                        {idx < steps.length - 1 ? <span className="journey-arrow" aria-hidden="true" /> : null}
                    </div>
                ))}
            </div>
            <div className="govt-resolved">{govt.resolved} resolved cases kept as quiet context.</div>
            <div className="sync-box">
                <div>
                    <strong>{govt.syncIssues} sync issues</strong>
                    <span>Review before next portal check.</span>
                </div>
                {govt.issues.length ? (
                    <ul>
                        {govt.issues.map((issue) => <li key={issue}>{issue}</li>)}
                    </ul>
                ) : null}
            </div>
        </Section>
    );
}

function PressureMap({ hotspots }) {
    return (
        <Section title="Constituency Pressure">
            <div className="map-card">
                <div className="map-shape" aria-label="Constituency pressure map">
                    <span className="map-road road-a" />
                    <span className="map-road road-b" />
                    <span className="map-road road-c" />
                </div>
                <div className="hotspot-list">
                    {hotspots.length === 0 ? (
                        <div><span>No location pressure yet</span><strong>0</strong></div>
                    ) : null}
                    {hotspots.map((spot) => (
                        <div key={spot.name}>
                            <span>{spot.name}</span>
                            <strong>{spot.count}</strong>
                        </div>
                    ))}
                </div>
            </div>
        </Section>
    );
}

function IssuePressure({ items }) {
    return (
        <Section title="Issue Pressure">
            <div className="pressure-list">
                {items.length === 0 ? (
                    <div className="pressure-row"><div><strong>No issue clusters yet</strong><span>&nbsp;</span></div><b>0</b></div>
                ) : null}
                {items.map((item) => (
                    <div key={item.title} className="pressure-row">
                        <div>
                            <strong>{item.title}</strong>
                            <span>{item.place}</span>
                        </div>
                        <b>{item.count}</b>
                    </div>
                ))}
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

function OfficePending({ items, onNavigate }) {
    return (
        <Section title="Office Pending">
            <div className="pending-list">
                {items.map((item) => (
                    <button
                        type="button"
                        key={item.key || item.label}
                        onClick={() => (item.href ? onNavigate(item.href) : undefined)}
                    >
                        {item.label}
                    </button>
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

function LocalSignals({ items }) {
    return (
        <section className="media-strip">
            <div className="op-section-head">
                <h2>Local Signals</h2>
            </div>
            <div className="media-list">
                {items.length === 0 ? (
                    <article><span>Local desk</span><p>No local coverage picked up yet.</p></article>
                ) : null}
                {items.map((item) => {
                    const body = (
                        <>
                            <span>{item.source}</span>
                            <p>{item.title}</p>
                        </>
                    );
                    return item.href ? (
                        <a
                            key={`${item.source}-${item.title}`}
                            href={item.href}
                            target="_blank"
                            rel="noreferrer noopener"
                        >
                            {body}
                        </a>
                    ) : (
                        <article key={`${item.source}-${item.title}`}>{body}</article>
                    );
                })}
            </div>
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

            <AttentionStrip items={data.attention} />

            {/* Desktop (>=1440): two independent vertical columns with their own
                flow/gap so each section starts as soon as the one above it ends.
                Below that the two wrappers flatten (display:contents) and the
                sections re-flow into the approved responsive stack (see the
                max-width:1439 media block). */}
            <div className="overview-columns">
                <div className="overview-col overview-col-left">
                    <AttentionQueue rows={data.queue} onOpenCase={openCase} onRunAction={runAction} />
                    <IssuePressure items={data.issuePressure} />
                    <OfficePending items={data.officePending} onNavigate={go} />
                </div>
                <div className="overview-col overview-col-right">
                    <GovernmentTracking govt={data.govt} />
                    <PressureMap hotspots={data.hotspots} />
                    <TodayAgenda items={data.today} />
                    <RecentMovement items={data.movement} />
                </div>
            </div>

            <LocalSignals items={data.media} />

            <style>{`
                .overview-dashboard {
                    min-height: 100dvh;
                    background: ${C.bg};
                    color: ${C.ink};
                    font-family: ${SANS};
                    padding: 30px 34px 48px;
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
                    margin-bottom: 18px;
                }

                .overview-kicker,
                .case-meta,
                .queue-header,
                .attention-label,
                .state-cell,
                .action-cell button,
                .action-cell .action-none,
                .mobile-queue-footer,
                .movement-row span,
                .agenda-row span,
                .media-list span {
                    font-family: ${MONO};
                }

                .overview-kicker {
                    margin: 0 0 8px;
                    color: ${C.greenDeep};
                    font-size: 10px;
                    letter-spacing: 0.1em;
                    text-transform: uppercase;
                }

                .overview-dashboard h1 {
                    margin: 0;
                    font-family: ${SERIF};
                    font-size: clamp(38px, 4.1vw, 68px);
                    font-weight: 700;
                    letter-spacing: -0.035em;
                    line-height: 0.95;
                    color: ${C.ink};
                }

                .overview-context {
                    margin: 10px 0 0;
                    color: ${C.muted};
                    font-size: 15px;
                }

                .attention-strip {
                    display: grid;
                    grid-template-columns: repeat(5, minmax(0, 1fr));
                    background: ${C.surface};
                    border: 1px solid ${C.border};
                    margin-bottom: 18px;
                }

                .attention-item {
                    min-height: 70px;
                    display: grid;
                    grid-template-columns: auto auto 1fr;
                    align-items: center;
                    gap: 8px;
                    padding: 14px 16px;
                    border-right: 1px solid ${C.border};
                }

                .attention-item:last-child {
                    border-right: 0;
                }

                .op-dot {
                    width: 7px;
                    height: 7px;
                    display: inline-block;
                    border-radius: 999px;
                }

                .attention-value {
                    font-family: ${SERIF};
                    font-size: 30px;
                    line-height: 1;
                    font-weight: 690;
                    letter-spacing: -0.04em;
                    color: ${C.ink};
                }

                .attention-label {
                    color: ${C.muted};
                    font-size: 10px;
                    line-height: 1.25;
                    text-transform: uppercase;
                    letter-spacing: 0.06em;
                }

                .overview-columns {
                    display: grid;
                    grid-template-columns: minmax(0, 1.68fr) minmax(324px, 0.92fr);
                    gap: 18px;
                    align-items: start;
                }

                .overview-col {
                    display: grid;
                    gap: 18px;
                    align-content: start;
                    min-width: 0;
                }

                .op-panel,
                .media-strip {
                    background: ${C.surface};
                    border: 1px solid ${C.border};
                }

                .op-section-head {
                    min-height: 58px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 16px;
                    padding: 15px 18px;
                    border-bottom: 1px solid ${C.border};
                }

                .op-section-head h2 {
                    margin: 0;
                    font-family: ${SERIF};
                    font-size: 24px;
                    font-weight: 670;
                    letter-spacing: -0.025em;
                    line-height: 1;
                    color: ${C.ink};
                }

                .op-section-head a {
                    color: ${C.greenDeep};
                    font-size: 12px;
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
                .mobile-queue-footer:active,
                .pending-list button:active {
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
                    column-gap: 10px;
                    align-items: center;
                }

                .queue-empty {
                    display: block;
                    padding: 20px 18px;
                    color: ${C.muted};
                    font-size: 13px;
                }

                .queue-header {
                    padding: 10px 18px;
                    color: ${C.faint};
                    font-size: 9.5px;
                    letter-spacing: 0.08em;
                    text-transform: uppercase;
                    border-bottom: 1px solid ${C.border};
                }

                .queue-row {
                    min-height: 98px;
                    padding: 14px 18px;
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
                    width: 6px;
                    height: 24px;
                    background: ${C.red};
                    display: inline-block;
                }

                .case-meta {
                    margin-top: 6px;
                    color: ${C.faint};
                    font-size: 10px;
                    line-height: 1.25;
                }

                .message-cell {
                    margin: 0;
                    color: #1F1D17;
                    font-size: 14.5px;
                    font-weight: 620;
                    line-height: 1.38;
                    letter-spacing: -0.01em;
                    display: -webkit-box;
                    -webkit-line-clamp: 2;
                    -webkit-box-orient: vertical;
                    overflow: hidden;
                }

                .issue-cell {
                    display: grid;
                    gap: 4px;
                    font-size: 12.5px;
                    line-height: 1.25;
                }

                .issue-cell strong {
                    color: #2E2A22;
                    font-weight: 650;
                }

                .issue-cell span,
                .govt-resolved,
                .sync-box span,
                .agenda-row p,
                .movement-row p,
                .media-list p {
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
                    padding: 5px 7px;
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
                    min-height: 30px;
                    border: 1px solid rgba(43, 110, 76, 0.34);
                    background: ${C.surface};
                    color: ${C.greenDeep};
                    cursor: pointer;
                    font-size: 10px;
                    font-weight: 650;
                    letter-spacing: 0.025em;
                    line-height: 1.18;
                    padding: 6px 8px;
                    text-align: left;
                    transition: border-color 150ms cubic-bezier(0.23, 1, 0.32, 1), background 150ms cubic-bezier(0.23, 1, 0.32, 1), color 150ms cubic-bezier(0.23, 1, 0.32, 1), transform 120ms cubic-bezier(0.23, 1, 0.32, 1);
                }

                .action-cell .action-none {
                    color: ${C.faint};
                    font-size: 12px;
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

                .journey {
                    position: relative;
                    display: grid;
                    gap: 0;
                    padding: 13px 16px 2px;
                }

                .journey-step {
                    position: relative;
                    display: grid;
                    grid-template-columns: 1fr;
                    padding-left: 15px;
                    align-items: start;
                }

                .journey-step::before {
                    content: '';
                    position: absolute;
                    left: 0;
                    top: 18px;
                    width: 6px;
                    height: 6px;
                    border-radius: 999px;
                    background: ${C.green};
                }

                .journey-step:not(:last-child)::after {
                    content: '';
                    position: absolute;
                    left: 2.5px;
                    top: 27px;
                    bottom: -2px;
                    width: 1px;
                    background: rgba(43, 110, 76, 0.22);
                }

                .journey-step > div {
                    border: 1px solid ${C.border};
                    background: ${C.surfaceWarm};
                    padding: 10px 12px;
                    display: flex;
                    align-items: baseline;
                    justify-content: space-between;
                    gap: 12px;
                }

                .journey-step span:first-child {
                    color: #514B3F;
                    font-size: 13px;
                }

                .journey-step strong {
                    font-family: ${SERIF};
                    font-size: 26px;
                    color: ${C.ink};
                    font-weight: 680;
                    letter-spacing: -0.04em;
                    line-height: 1;
                }

                .journey-arrow {
                    display: none;
                }

                .govt-resolved {
                    margin: 8px 16px 11px;
                    font-size: 11.5px;
                    line-height: 1.4;
                }

                .sync-box {
                    margin: 0 16px 15px;
                    background: ${C.rustSoft};
                    border: 1px solid rgba(188, 106, 54, 0.28);
                    padding: 11px 12px;
                }

                .sync-box strong {
                    display: block;
                    color: ${C.ink};
                    font-size: 13px;
                    margin-bottom: 3px;
                }

                .sync-box span,
                .sync-box li {
                    font-size: 11.5px;
                    line-height: 1.3;
                }

                .sync-box ul {
                    margin: 8px 0 0;
                    padding-left: 16px;
                    color: #514B3F;
                }

                .map-card {
                    padding: 10px 14px 12px;
                }

                .map-shape {
                    position: relative;
                    height: 214px;
                    background: ${C.greenSoft};
                    border: 1px solid ${C.borderStrong};
                    clip-path: polygon(13% 2%, 63% 6%, 91% 27%, 83% 70%, 59% 98%, 19% 88%, 3% 52%);
                    overflow: hidden;
                }

                .map-shape::before {
                    content: '';
                    position: absolute;
                    inset: 12px;
                    border: 1px solid rgba(36, 95, 69, 0.16);
                    clip-path: polygon(11% 8%, 75% 12%, 91% 45%, 64% 90%, 21% 80%, 3% 44%);
                }

                .map-road {
                    position: absolute;
                    height: 1px;
                    background: rgba(36, 95, 69, 0.22);
                    transform-origin: left center;
                }

                .road-a { width: 190px; left: 18%; top: 40%; transform: rotate(17deg); }
                .road-b { width: 150px; left: 30%; top: 72%; transform: rotate(-25deg); }
                .road-c { width: 135px; left: 48%; top: 24%; transform: rotate(68deg); }

                .hotspot-list {
                    display: grid;
                    gap: 0;
                    margin-top: 10px;
                }

                .hotspot-list div {
                    display: flex;
                    justify-content: space-between;
                    align-items: baseline;
                    border-top: 1px solid ${C.border};
                    padding-top: 7px;
                    padding-bottom: 7px;
                    color: #514B3F;
                    font-size: 12.5px;
                }

                .hotspot-list strong {
                    font-family: ${MONO};
                    color: ${C.ink};
                    font-size: 12px;
                }

                .pressure-list,
                .agenda-list,
                .movement-list {
                    display: grid;
                }

                .pressure-row {
                    display: grid;
                    grid-template-columns: minmax(160px, 0.78fr) minmax(200px, 1fr) auto;
                    gap: 18px;
                    align-items: center;
                    padding: 14px 18px;
                    border-bottom: 1px solid ${C.border};
                }

                .pressure-row:last-child,
                .agenda-row:last-child,
                .movement-row:last-child {
                    border-bottom: 0;
                }

                .pressure-row div {
                    display: grid;
                    gap: 4px;
                }

                .pressure-row strong {
                    color: ${C.ink};
                    font-size: 14px;
                    font-weight: 650;
                }

                .pressure-row span {
                    color: ${C.faint};
                    font-size: 12px;
                }

                .pressure-row b {
                    font-family: ${SERIF};
                    color: ${C.greenDeep};
                    font-size: 26px;
                    font-weight: 700;
                    letter-spacing: -0.04em;
                }

                .agenda-row,
                .movement-row {
                    display: grid;
                    align-items: center;
                    gap: 12px;
                    padding: 13px 18px;
                    border-bottom: 1px solid ${C.border};
                    text-decoration: none;
                }

                .agenda-row {
                    grid-template-columns: 52px 1fr;
                }

                .movement-row {
                    grid-template-columns: 48px auto 1fr;
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
                    font-size: 13px;
                    line-height: 1.35;
                }

                .pending-list {
                    display: grid;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    gap: 0;
                }

                .pending-list button {
                    min-height: 92px;
                    border: 0;
                    border-right: 1px solid ${C.border};
                    background: transparent;
                    color: ${C.ink};
                    cursor: pointer;
                    font-family: ${SANS};
                    font-size: 14px;
                    font-weight: 560;
                    line-height: 1.35;
                    padding: 16px 18px;
                    text-align: left;
                    transition: background 150ms cubic-bezier(0.23, 1, 0.32, 1), transform 120ms cubic-bezier(0.23, 1, 0.32, 1);
                }

                .pending-list button:last-child {
                    border-right: 0;
                }

                @media (hover: hover) and (pointer: fine) {
                    .pending-list button:hover {
                        background: ${C.surfaceWarm};
                    }
                }

                .media-strip {
                    margin-top: 18px;
                }

                .media-list {
                    display: grid;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                }

                .media-list article,
                .media-list a {
                    min-height: 92px;
                    padding: 16px 18px;
                    border-right: 1px solid ${C.border};
                    text-decoration: none;
                    display: block;
                    transition: background 150ms cubic-bezier(0.23, 1, 0.32, 1);
                }

                @media (hover: hover) and (pointer: fine) {
                    .media-list a:hover {
                        background: ${C.surfaceWarm};
                    }
                }

                .media-list article:last-child,
                .media-list a:last-child {
                    border-right: 0;
                }

                .media-list span {
                    display: block;
                    color: ${C.faint};
                    font-size: 10px;
                    letter-spacing: 0.04em;
                    text-transform: uppercase;
                    margin-bottom: 8px;
                }

                .media-list p {
                    margin: 0;
                    color: ${C.ink};
                    font-size: 14px;
                    font-weight: 560;
                    line-height: 1.35;
                }

                /* Below ~1440 the fixed 220px app rail leaves too little room for
                   the intended ~65/35 two-column composition, so fall back to the
                   approved responsive stack: Attention Queue full width, then
                   Government Tracking + Constituency Pressure paired where space
                   allows, then every other section full width, all in the
                   approved order. The two column wrappers are flattened with
                   display:contents so order can interleave their children;
                   explicit flex-basis keeps every card using the full workspace
                   width (no narrow partial-width cards). */
                @media (max-width: 1439px) {
                    .overview-dashboard {
                        padding: 26px 24px 42px;
                    }

                    .overview-columns {
                        display: flex;
                        flex-wrap: wrap;
                        align-items: flex-start;
                        gap: 18px;
                    }

                    .overview-col {
                        display: contents;
                    }

                    .overview-col-left > :nth-child(1) { order: 1; flex: 1 1 100%; }                       /* Attention Queue */
                    .overview-col-right > :nth-child(1) { order: 2; flex: 1 1 calc(50% - 9px); min-width: 0; }  /* Government Tracking */
                    .overview-col-right > :nth-child(2) { order: 3; flex: 1 1 calc(50% - 9px); min-width: 0; }  /* Constituency Pressure */
                    .overview-col-left > :nth-child(2) { order: 4; flex: 1 1 100%; }                       /* Issue Pressure */
                    .overview-col-right > :nth-child(3) { order: 5; flex: 1 1 100%; }                      /* Today */
                    .overview-col-left > :nth-child(3) { order: 6; flex: 1 1 100%; }                       /* Office Pending */
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
                        font-size: 14px;
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
                       Constituency Pressure go full width, keeping the stack. */
                    .overview-col-right > :nth-child(1),
                    .overview-col-right > :nth-child(2) {
                        flex-basis: 100%;
                    }

                    .attention-strip {
                        grid-template-columns: repeat(3, minmax(0, 1fr));
                    }

                    .attention-item:nth-child(3) {
                        border-right: 0;
                    }

                    .attention-item:nth-child(n + 4) {
                        border-top: 1px solid ${C.border};
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

                    .map-shape {
                        height: 246px;
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

                    .attention-strip {
                        grid-template-columns: repeat(2, minmax(0, 1fr));
                    }

                    .attention-item,
                    .attention-item:nth-child(3) {
                        border-right: 0;
                    }

                    .attention-item {
                        min-height: 54px;
                        grid-template-columns: auto auto;
                        align-content: center;
                        gap: 4px 7px;
                        padding: 10px 12px;
                    }

                    .attention-item:nth-child(odd) {
                        border-right: 1px solid ${C.border};
                    }

                    .attention-item:nth-child(n + 3) {
                        border-top: 1px solid ${C.border};
                    }

                    .attention-item:last-child {
                        grid-column: 1 / -1;
                    }

                    .attention-label {
                        grid-column: 2;
                        font-size: 9px;
                    }

                    .attention-value {
                        font-size: 24px;
                    }

                    .op-section-head {
                        padding: 14px;
                    }

                    .op-section-head h2 {
                        font-size: 22px;
                    }

                    .queue-row {
                        grid-template-columns: 1fr;
                        min-height: 0;
                        padding: 14px;
                        row-gap: 10px;
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
                        font-size: 13.75px;
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

                    .journey,
                    .map-card {
                        padding-left: 14px;
                        padding-right: 14px;
                    }

                    .journey-arrow {
                        display: none;
                    }

                    .journey-step {
                        grid-template-columns: 1fr;
                        margin-bottom: 8px;
                    }

                    .sync-box,
                    .govt-resolved {
                        margin-left: 14px;
                        margin-right: 14px;
                    }

                    .pressure-row {
                        grid-template-columns: 1fr auto;
                        gap: 7px 12px;
                        padding: 14px;
                    }

                    .pending-list,
                    .media-list {
                        grid-template-columns: 1fr;
                    }

                    .pending-list button,
                    .media-list article,
                    .media-list a {
                        border-right: 0;
                        border-bottom: 1px solid ${C.border};
                    }

                    .pending-list button:last-child,
                    .media-list article:last-child,
                    .media-list a:last-child {
                        border-bottom: 0;
                    }
                }
            `}</style>
        </main>
    );
}
