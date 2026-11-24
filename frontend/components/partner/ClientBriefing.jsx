'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { partnerClientBriefing } from '@/lib/partnerApi';
import { fmtCount, fmtDate, periodKey, periodPhrase } from '@/lib/partnerFormat';
import {
    briefingEyebrow, buildBriefing, change, changeLabel, changeTone, funnelCallout, joinNames,
} from '@/lib/partnerBriefing';
import { ErrorState, Icon, PeriodSelect, SectionHead, Skel } from '@/components/partner/ui';

const TOP_LOCALITIES = 6;

const MOMENTUM = [
    { key: 'received', label: 'Complaints received', goodWhen: 'down', color: 'var(--s2)' },
    { key: 'filed', label: 'Filed with government', goodWhen: 'up', color: 'var(--s1)' },
    { key: 'resolved_by_government', label: 'Resolved by government', goodWhen: 'up', color: 'var(--go)' },
    { key: 'other_actions', label: 'Other actions taken', goodWhen: 'up', color: 'var(--s1)', hint: 'Letters, referrals, local fixes, information given' },
    { key: 'pending', label: 'Pending', goodWhen: 'down', color: 'var(--crit)', hint: 'No action yet', crit: true },
];

function Spark({ values, color, width = 64, height = 22 }) {
    if (!values || values.length < 2) return null;
    const max = Math.max(...values);
    const min = Math.min(...values);
    const x = (i) => 2 + (i * (width - 4)) / (values.length - 1);
    const y = (v) => height - 3 - ((v - min) / ((max - min) || 1)) * (height - 6);
    const d = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
    return (
        <svg width={width} height={height} aria-hidden="true" className="pd-spark">
            <path d={d} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
        </svg>
    );
}

function Change({ now, previous, goodWhen }) {
    const label = changeLabel(now, previous);
    if (!label) return null;
    const tone = changeTone(now, previous, goodWhen);
    return <span className={`pd-chg ${tone || 'flat'}`}>{label}</span>;
}

function heatColor(value, max) {
    const t = max ? value / max : 0;
    const a = [247, 240, 234];
    const b = [158, 50, 24];
    return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * t * 0.92)).join(',')})`;
}

function BriefingPanel({ briefing, period, onOpenReports }) {
    const { headline, points, text } = useMemo(() => buildBriefing(briefing), [briefing]);
    const [copied, setCopied] = useState('');

    async function copy() {
        try {
            await navigator.clipboard.writeText(text);
            setCopied('Briefing copied');
        } catch {
            setCopied('Copy is not available in this browser');
        }
        setTimeout(() => setCopied(''), 1800);
    }

    const wins = briefing.wins || [];
    return (
        <section className="pd-panel pd-brief" aria-label="Briefing">
            <div className="pd-brief-l">
                <div className="pd-eyebrow">{briefingEyebrow(period)}</div>
                <p className="pd-headline">
                    {headline.lead}{headline.emphasis ? <> <em>{headline.emphasis}</em></> : null}
                </p>
                {points.length ? (
                    <ul className="pd-points">
                        {points.map((p) => (
                            <li key={p.strong}><span className={`pd-dot ${p.tone}`} aria-hidden="true" /><span><b>{p.strong}</b>{p.rest}</span></li>
                        ))}
                    </ul>
                ) : null}
                <div className="pd-brief-actions">
                    <button type="button" className="pd-btn sm" onClick={copy}><Icon name="copy" size={15} /> Copy briefing</button>
                    <button type="button" className="pd-btn sm" onClick={onOpenReports}><Icon name="report" size={15} /> Client report</button>
                    <span role="status" aria-live="polite" className="pd-secsub" style={{ margin: 0 }}>{copied}</span>
                </div>
            </div>
            <div className="pd-brief-r" aria-labelledby="wins-h">
                <div className="pd-eyebrow" id="wins-h">Wins to publicise</div>
                <div className="pd-secsub" style={{ marginTop: 4 }}>Resolved by government in {periodPhrase(period)}, by issue and locality</div>
                {wins.length ? (
                    <ul className="pd-wins">
                        {wins.map((w) => (
                            <li key={w.name}>
                                <span className="n num">{fmtCount(w.count)}</span>
                                <span><span className="t">{w.name}</span>{w.localities.length ? <span className="d">{joinNames(w.localities)}</span> : null}</span>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="pd-secsub" style={{ margin: '14px 0' }}>No grievances were resolved by government in this period yet.</p>
                )}
                <div className="pd-wintotal"><span>Total resolved by government</span><b className="num">{fmtCount(briefing.wins_total)}</b></div>
            </div>
        </section>
    );
}

function Momentum({ briefing }) {
    const m = briefing.momentum;
    return (
        <section className="pd-panel pd-kpis pd-mom" style={{ '--n': MOMENTUM.length }} aria-label="Momentum">
            {MOMENTUM.map((k) => {
                const v = m[k.key];
                return (
                    <div className="pd-kpi" key={k.key}>
                        <div className="pd-kpi-label">{k.label}</div>
                        <div className="pd-kpi-val num" style={k.crit && v.now ? { color: 'var(--crit)' } : undefined}>{fmtCount(v.now)}</div>
                        <div className="pd-kpi-foot">
                            <Change now={v.now} previous={v.previous} goodWhen={k.goodWhen} />
                            {v.previous !== null && v.previous !== undefined ? <span>vs {fmtCount(v.previous)}</span> : null}
                            <Spark values={v.trend} color={k.color} width={56} height={20} />
                        </div>
                        {k.hint ? <div className="pd-kpi-hint">{k.hint}</div> : null}
                    </div>
                );
            })}
        </section>
    );
}

function Issues({ briefing }) {
    const issues = briefing.issues || [];
    const hasCompare = !!briefing.compare;
    return (
        <section className="pd-panel pd-pad" aria-labelledby="iss-h">
            <SectionHead id="iss-h" title="What's rising" sub={hasCompare ? 'Complaints by issue, this period vs the previous one' : 'Complaints by issue'} />
            {issues.length ? (
                <div className="pd-tablewrap">
                    <table className="pd-itable">
                        <thead><tr>
                            <th scope="col">Issue</th><th scope="col" className="r">Now</th>
                            {hasCompare ? <><th scope="col" className="r pd-hide-sm">Before</th><th scope="col" className="r">Change</th></> : null}
                            <th scope="col" className="r pd-hide-sm">Trend</th>
                        </tr></thead>
                        <tbody>
                            {issues.map((i) => {
                                const c = change(i.count, i.previous);
                                const spike = hasCompare && i.count >= 3 && (i.previous === 0 || (c !== null && c >= 0.5));
                                return (
                                    <tr key={i.name}>
                                        <td><b>{i.name}</b>{spike ? <span className="pd-spike">Spike</span> : null}</td>
                                        <td className="r num">{fmtCount(i.count)}</td>
                                        {hasCompare ? (
                                            <>
                                                <td className="r num pd-hide-sm muted">{fmtCount(i.previous)}</td>
                                                <td className="r">
                                                    <span className="pd-chgcell">
                                                        <Change now={i.count} previous={i.previous} goodWhen="down" />
                                                        {c !== null ? <span className="bar" aria-hidden="true" style={{ width: `${Math.min(60, Math.abs(c) * 60)}px`, background: c > 0 ? '#D9A08F' : '#9CC6B2' }} /> : null}
                                                    </span>
                                                </td>
                                            </>
                                        ) : null}
                                        <td className="r pd-hide-sm"><Spark values={i.trend} color={c !== null && c > 0.3 ? 'var(--crit)' : 'var(--s1)'} width={72} /></td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            ) : <p className="pd-secsub">No complaints in this period.</p>}
        </section>
    );
}

function Hotspots({ briefing }) {
    const hot = briefing.hotspots;
    const [all, setAll] = useState(false);
    const [query, setQuery] = useState('');
    const rows = hot.localities || [];
    const max = Math.max(1, ...rows.flatMap((r) => r.counts));
    const q = query.trim().toLowerCase();
    const shown = all ? rows.filter((r) => !q || r.name.toLowerCase().includes(q)) : rows.slice(0, TOP_LOCALITIES);
    const cols = { gridTemplateColumns: `minmax(124px, 1.5fr) repeat(${hot.columns.length}, minmax(0, 1fr))` };

    return (
        <section className="pd-panel pd-pad" aria-labelledby="hot-h">
            <SectionHead id="hot-h" title="Hotspots" sub="Complaints by locality and issue" />
            {rows.length && hot.columns.length ? (
                <>
                    {all ? (
                        <div className="pd-hotbar">
                            <input type="search" className="pd-input" placeholder={`Search ${rows.length} localities`} aria-label="Search localities"
                                value={query} onChange={(e) => setQuery(e.target.value)} style={{ height: 32 }} />
                            <span className="pd-secsub" style={{ margin: 0, whiteSpace: 'nowrap' }}>{shown.length} shown</span>
                        </div>
                    ) : null}
                    <div className="pd-heat" style={cols}>
                        <span className="h">Locality</span>
                        {hot.columns.map((c) => <span key={c} className="h c-h" title={c}>{c}</span>)}
                    </div>
                    <div className={all ? 'pd-hotscroll' : undefined}>
                        <div className="pd-heat" style={cols} aria-label="Complaints by locality and issue">
                            {shown.map((r) => (
                                <div key={r.name} className="pd-heatrow" style={{ display: 'contents' }}>
                                    <span className="rowh" title={r.name}>{r.name}</span>
                                    {r.counts.map((v, ci) => (
                                        <span key={hot.columns[ci]} className="c num" title={`${r.name} · ${hot.columns[ci]}: ${v} complaint${v === 1 ? '' : 's'}`}
                                            style={{ background: heatColor(v, max), color: v / max > 0.55 ? '#fff' : 'var(--ink)' }}>{v}</span>
                                    ))}
                                </div>
                            ))}
                            {!shown.length ? <span className="pd-secsub" style={{ gridColumn: '1 / -1', padding: '10px 0' }}>No locality matches “{query}”.</span> : null}
                        </div>
                    </div>
                    {rows.length > TOP_LOCALITIES ? (
                        <button type="button" className="pd-btn sm pd-seeall" aria-expanded={all} onClick={() => { setAll(!all); setQuery(''); }}>
                            {all ? `Show top ${TOP_LOCALITIES}` : `See all ${rows.length} localities →`}
                        </button>
                    ) : null}
                    <div className="pd-scale" aria-hidden="true">
                        <span>Fewer</span>{[0, 0.25, 0.5, 0.75, 1].map((t) => <i key={t} style={{ background: heatColor(t * max, max) }} />)}<span>More</span>
                    </div>
                </>
            ) : <p className="pd-secsub">No complaints with a mapped locality in this period.</p>}
            <p className="pd-secsub" style={{ marginTop: 10 }}>
                Locality names come from the office&apos;s geography mapping, never from free-text addresses.
                {hot.unmapped ? ` ${fmtCount(hot.unmapped)} complaint${hot.unmapped === 1 ? ' has' : 's have'} no mapped locality.` : ''}
            </p>
        </section>
    );
}

function Delivery({ briefing }) {
    const f = briefing.funnel;
    const stages = [
        ['Received', f.received],
        ['Action taken', f.action_taken],
        ['Filed with government', f.filed],
        ['Resolved by government', f.resolved_by_government],
    ];
    const max = Math.max(1, f.received);
    const callout = funnelCallout(f);
    return (
        <section className="pd-panel pd-pad" aria-labelledby="del-h">
            <SectionHead id="del-h" title="From complaint to government action" sub="Grievances received in this period, and where they stand now" />
            <div className="pd-delivery">
                <div className="pd-funnel">
                    {stages.map(([label, v], i) => (
                        <div key={label} className={`fr${i === 2 && callout?.title === 'The drop is at filing.' ? ' stuck' : ''}`}>
                            <span>{label}</span>
                            <span className="bar" aria-hidden="true"><b style={{ width: `${(v / max) * 100}%` }} /></span>
                            <span className="v num">{fmtCount(v)}</span>
                        </div>
                    ))}
                </div>
                {callout ? (
                    <div className={`pd-callout ${callout.tone}`}>
                        <Icon name="alert" size={18} /><span><b>{callout.title}</b> {callout.body}</span>
                    </div>
                ) : null}
            </div>
        </section>
    );
}

export default function ClientBriefing({ seatId, period, onPeriodChange, onOpenReports, onUnauthorized }) {
    const [data, setData] = useState(null);
    const [status, setStatus] = useState('loading');
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        setStatus('loading');
        setError('');
        try {
            const res = await partnerClientBriefing(seatId, period);
            setData(res.briefing);
            setStatus('ready');
        } catch (err) {
            if (err.status === 401) {
                onUnauthorized?.();
                return;
            }
            setError(err.message || 'The briefing could not be loaded.');
            setStatus('error');
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [seatId, periodKey(period)]);

    useEffect(() => { load(); }, [load]);

    const compare = data?.compare;
    return (
        <div className="pd-briefing">
            <div className="pd-pagehead" style={{ marginBottom: 14 }}>
                <div className="pd-secsub" style={{ margin: 0 }}>
                    Grievances received in {periodPhrase(period)}
                    {compare ? `, compared with ${fmtDate(compare.from)} – ${fmtDate(compare.to)}` : ''} · counts only, no citizen details
                </div>
                <PeriodSelect period={period} onChange={onPeriodChange} />
            </div>

            {status === 'error' ? <ErrorState title="The briefing is unavailable right now." message={error} onRetry={load} /> : null}
            {status === 'loading' && !data ? (
                <div aria-busy="true" aria-label="Loading briefing" style={{ display: 'grid', gap: 20 }}>
                    <Skel h={260} /><Skel h={120} /><Skel h={320} />
                </div>
            ) : null}

            {data && status !== 'error' ? (
                <div style={{ display: 'grid', gap: 22, opacity: status === 'loading' ? 0.6 : 1 }} aria-busy={status === 'loading'}>
                    <BriefingPanel briefing={data} period={period} onOpenReports={onOpenReports} />
                    <Momentum briefing={data} />
                    <div className="pd-grid21">
                        <Issues briefing={data} />
                        <Hotspots briefing={data} key={periodKey(period)} />
                    </div>
                    <Delivery briefing={data} />
                    <p className="pd-secsub" style={{ margin: 0 }}>
                        All figures count grievances received in the period and where they stand now. Individual grievances,
                        complaint text and citizen contact details are never shown to partners.
                    </p>
                </div>
            ) : null}
        </div>
    );
}
