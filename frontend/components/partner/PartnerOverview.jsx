'use client';

import { useCallback, useEffect, useState } from 'react';
import { partnerClientOverview } from '@/lib/partnerApi';
import { fmtCount, fmtDays, fmtPct, periodPhrase } from '@/lib/partnerFormat';
import { Badge, ErrorState, Kpis, RankedBars, SectionHead, Skel } from './ui';

const PIPELINE = [
    ['ready', 'Ready to file', 'Prepared, not yet filed'],
    ['submitted', 'Submitted', 'Filed on the portal'],
    ['registered', 'Registered', 'Portal reference issued'],
    ['forwarded', 'Forwarded', 'Sent to a department'],
    ['awaiting_action', 'Awaiting action', 'With the department'],
];
const OUTCOMES = [
    ['resolved', 'Resolved', 'var(--go)'],
    ['disposed', 'Disposed', 'var(--s2)'],
    ['rejected', 'Rejected', 'var(--crit)'],
];

function count(list, key) {
    const hit = (list || []).find((x) => x.key === key);
    return hit ? Number(hit.value) || 0 : 0;
}

/**
 * Client Overview: work waiting on the office, the government filing pipeline, and where pressure comes from.
 * Counts only — partners never see individual grievances or citizen details.
 */
export default function PartnerOverview({ seatId, summary, period, onUnauthorized }) {
    const [overview, setOverview] = useState(null);
    const [status, setStatus] = useState('loading');
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        setStatus('loading');
        setError('');
        try {
            const res = await partnerClientOverview(seatId);
            setOverview(res.overview);
            setStatus('ready');
        } catch (err) {
            if (err.status === 401 && onUnauthorized) return onUnauthorized();
            setError(err.message || 'The overview could not be loaded.');
            setStatus('error');
        }
    }, [seatId, onUnauthorized]);

    useEffect(() => { load(); }, [load]);

    if (status === 'error') return <ErrorState title="The overview is unavailable right now." message={error} onRetry={load} />;
    if (status === 'loading' || !overview) {
        return (
            <div aria-busy="true" aria-label="Loading overview" style={{ display: 'grid', gap: 20 }}>
                <Skel h={112} /><div className="pd-grid pd-g32"><Skel h={230} /><Skel h={230} /></div><Skel h={260} />
            </div>
        );
    }

    const gt = overview.government_tracking || {};
    const att = overview.attention_counts || [];
    const office = overview.office_pending || [];
    const attention = [
        { key: 'needs_review', title: 'Needs review', desc: 'New threads the office has not reviewed yet', value: count(att, 'needs_review'), tone: 'crit' },
        { key: 'unassigned', title: 'Needs an owner', desc: 'Threads not yet assigned to a staff member', value: count(office, 'unassigned'), tone: 'warn' },
        { key: 'needs_location', title: 'Needs location', desc: 'Location could not be matched to a ward or segment', value: count(att, 'needs_location'), tone: 'warn' },
    ];
    const waiting = attention.reduce((a, x) => a + x.value, 0);
    const pmax = Math.max(1, ...PIPELINE.map(([k]) => gt[k] || 0));
    const outTotal = OUTCOMES.reduce((a, [k]) => a + (gt[k] || 0), 0);
    const issues = (overview.issue_pressure || []).map((i) => ({ key: i.title, label: i.title, count: i.count }));
    const areas = (overview.constituency_pressure || []).map((a) => ({ key: a.name, label: a.name, count: a.count }));
    const issueTotal = issues.reduce((a, i) => a + i.count, 0);
    const areaTotal = areas.reduce((a, i) => a + i.count, 0);

    return (
        <div>
            {summary ? (
                <section aria-labelledby="pd-perf-h">
                    <SectionHead id="pd-perf-h" title="Constituency performance" sub={`Grievances received in ${periodPhrase(period)} · change the period on Analytics`} />
                    <Kpis label="Constituency performance" items={[
                        { label: 'Received', value: fmtCount(summary.total) },
                        { label: 'Resolved', value: fmtCount(summary.resolved), foot: `${fmtCount(summary.open)} still open` },
                        { label: 'Resolution rate', value: fmtPct(summary.resolution_rate) },
                        { label: 'Avg. time to resolve', value: fmtDays(summary.avg_resolution_days) },
                    ]} />
                </section>
            ) : null}

            <div className="pd-grid pd-g32 pd-mt">
                <section className="pd-panel" aria-labelledby="pd-req-h">
                    <div style={{ padding: '18px 20px 4px' }}>
                        <SectionHead id="pd-req-h" title="Requires attention" sub={`Work waiting on the office · ${waiting} threads`}
                            right={summary?.critical ? <Badge tone="crit">{summary.critical} critical</Badge> : null} />
                    </div>
                    <ul className="pd-att">
                        {attention.map((a) => (
                            <li key={a.key}>
                                <div className="row" style={{ gridTemplateColumns: 'auto minmax(0, 1fr) auto' }}>
                                    <span className={`pd-dot ${a.value ? a.tone : 'neutral'}`} aria-hidden="true" />
                                    <div><div className="t">{a.title}</div><div className="d">{a.desc}</div></div>
                                    <div className={`n num ${a.tone === 'crit' && a.value ? 'crit' : ''}`} data-testid={`attention-${a.key}`}>{a.value}</div>
                                </div>
                            </li>
                        ))}
                    </ul>
                </section>
                <section className="pd-panel pd-pad" aria-labelledby="pd-upd-h">
                    <SectionHead id="pd-upd-h" title="Updates and office workload" sub="Information — no action needed from you" />
                    <div className="pd-kv">
                        <div>Government updates received</div><div className="v num">{count(att, 'govt_updates')}</div>
                        <div>New letters awaiting intake</div><div className="v num">{count(office, 'letters')}</div>
                        <div>Drafts awaiting approval</div><div className="v num">{count(office, 'drafts')}</div>
                    </div>
                </section>
            </div>

            <section className="pd-panel pd-pad pd-mt" aria-labelledby="pd-gov-h">
                <SectionHead id="pd-gov-h" title="Government grievance tracking"
                    sub="What the government portals report. This is separate from Needle's own resolution figures above."
                    right={(
                        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                            <span className="pd-hchip"><span className={`pd-dot ${gt.awaiting_verification ? 'warn' : 'go'}`} aria-hidden="true" />
                                <span>Awaiting verification</span> <b className="num" data-testid="govt-awaiting_verification">{fmtCount(gt.awaiting_verification)}</b></span>
                            <span className="pd-hchip"><span className={`pd-dot ${gt.sync_issues ? 'crit' : 'go'}`} aria-hidden="true" />
                                <span>Portal sync issues</span> <b className="num">{fmtCount(gt.sync_issues)}</b></span>
                        </div>
                    )} />
                <div className="pd-pipe" role="list" aria-label="Government filing stages">
                    {PIPELINE.map(([k, label, sub], i) => (
                        <div key={k} className={`pd-stage ${k === 'awaiting_action' && gt[k] ? 'hl' : ''}`} role="listitem">
                            <div className="no">0{i + 1}</div>
                            <div className="k">{label}</div>
                            <div className="v num" data-testid={`govt-${k}`}>{fmtCount(gt[k])}</div>
                            <div className="s">{sub}</div>
                            <div className="meter"><b style={{ width: `${((gt[k] || 0) / pmax) * 100}%` }} /></div>
                        </div>
                    ))}
                </div>
                <div style={{ marginTop: 20 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 }}>
                        <b style={{ fontSize: 13 }}>Outcomes reported by portals</b>
                        <span className="muted num" style={{ fontSize: 12.5 }}>{fmtCount(outTotal)} closed filings</span>
                    </div>
                    <div className="pd-split" role="img" aria-label={OUTCOMES.map(([k, l]) => `${l} ${gt[k] || 0}`).join(', ')}>
                        {outTotal ? OUTCOMES.map(([k, , color]) => <b key={k} style={{ width: `${((gt[k] || 0) / outTotal) * 100}%`, background: color }} />) : null}
                    </div>
                    <div className="pd-ol">
                        {OUTCOMES.map(([k, l, color]) => <span key={k}><i style={{ background: color }} />{l} <b className="num">{fmtCount(gt[k])}</b></span>)}
                    </div>
                </div>
            </section>

            <div className="pd-grid pd-g11 pd-mt">
                <section className="pd-panel pd-pad" aria-labelledby="pd-iss-h">
                    <SectionHead id="pd-iss-h" title="Issue pressure" sub="Live grievance threads by category" />
                    <RankedBars items={issues} total={issueTotal} empty="No grievances yet." />
                </section>
                <section className="pd-panel pd-pad" aria-labelledby="pd-area-h">
                    <SectionHead id="pd-area-h" title="Constituency pressure" sub="Live threads by assembly segment or area" />
                    <RankedBars items={areas} total={areaTotal} empty="No area breakdown available yet." />
                </section>
            </div>
            <p className="pd-note">Counts of grievance threads. Individual grievances and citizen details are not shown to partners.</p>
        </div>
    );
}
