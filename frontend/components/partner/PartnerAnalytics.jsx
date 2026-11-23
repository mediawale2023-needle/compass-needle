'use client';

import { useEffect, useState } from 'react';
import { partnerClients } from '@/lib/partnerApi';
import { fmtCount, fmtDays, fmtPct } from '@/lib/partnerFormat';
import { BarChart, Legend, LineChart, weekLabel } from './charts';
import { Kpis, PeriodSelect, RankedBars, SectionHead } from './ui';

/** Portfolio averages for comparison, from the same aggregate /clients endpoint the portfolio page uses. */
function usePortfolioBenchmark(days) {
    const [bench, setBench] = useState(null);
    useEffect(() => {
        let cancelled = false;
        setBench(null);
        partnerClients(days).then((d) => {
            if (cancelled) return;
            const live = (d.clients || []).filter((c) => c.status === 'active' && c.summary);
            const p = d.portfolio || {};
            const resolvedWeighted = live.filter((c) => c.summary.avg_resolution_days !== null && c.summary.avg_resolution_days !== undefined);
            const wSum = resolvedWeighted.reduce((a, c) => a + c.summary.resolved, 0);
            setBench({
                clients: live.length,
                rate: p.total ? p.resolved / p.total : null,
                avgDays: wSum ? resolvedWeighted.reduce((a, c) => a + c.summary.avg_resolution_days * c.summary.resolved, 0) / wSum : null,
                criticalShare: p.total ? p.critical / p.total : null,
                weekly: p.weekly || [],
            });
        }).catch(() => { if (!cancelled) setBench(null); });
        return () => { cancelled = true; };
    }, [days]);
    return bench;
}

export default function PartnerAnalytics({ summary: s, days, onDaysChange, clientLabel }) {
    const bench = usePortfolioBenchmark(days);
    const weekly = s.weekly || [];
    const labels = weekly.map((w) => weekLabel(w.week_ending));
    const rateSeries = weekly.map((w) => (w.received ? w.resolved / w.received : null));
    const benchWeeks = Object.fromEntries((bench?.weekly || []).map((w) => [w.week_ending, w]));
    const benchRate = weekly.map((w) => {
        const b = benchWeeks[w.week_ending];
        return b && b.received ? b.resolved / b.received : null;
    });
    const categories = (s.top_categories || []).map((c) => ({ key: c.name, label: c.name, count: c.count }));
    const places = (s.top_locations || []).map((c) => ({ key: c.name, label: c.name, count: c.count }));
    const criticalShare = s.total ? s.critical / s.total : null;

    const compare = bench ? [
        { label: 'Resolution rate', v: s.resolution_rate, p: bench.rate, f: (v) => fmtPct(v), better: 'up' },
        { label: 'Avg. time to resolve', v: s.avg_resolution_days, p: bench.avgDays, f: (v) => (v === null || v === undefined ? '—' : `${v.toFixed(1)}d`), better: 'down' },
        { label: 'Critical share of received', v: criticalShare, p: bench.criticalShare, f: (v) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`), better: 'down' },
    ] : [];

    return (
        <div>
            <div className="pd-pagehead" style={{ marginBottom: 18 }}>
                <div>
                    <h2 className="pd-sec" style={{ fontSize: 17 }}>Performance analysis</h2>
                    <div className="pd-secsub">Grievances received in the last {days} days. Weekly charts always cover the last 8 weeks.</div>
                </div>
                <PeriodSelect days={days} onChange={onDaysChange} />
            </div>

            <Kpis label={`Headline numbers, last ${days} days`} items={[
                { label: 'Received', value: fmtCount(s.total) },
                { label: 'Resolved', value: fmtPct(s.resolution_rate), foot: `${fmtCount(s.resolved)} grievances` },
                { label: 'Still open', value: fmtCount(s.open) },
                { label: 'Critical', value: fmtCount(s.critical), tone: s.critical >= 5 ? 'crit' : undefined },
                { label: 'Avg. to resolve', value: fmtDays(s.avg_resolution_days) },
            ]} />

            <div className="pd-grid pd-g11 pd-mt">
                <section className="pd-panel pd-pad" aria-labelledby="pd-vol-h">
                    <SectionHead id="pd-vol-h" title="Grievance volume" sub="Received and resolved, by week ending"
                        right={<Legend items={[{ label: 'Received', color: 'var(--s2)' }, { label: 'Resolved', color: 'var(--s1)' }]} />} />
                    <BarChart labels={labels} width={580} height={280}
                        ariaLabel={`Weekly grievances, last 8 weeks. ${weekly.map((w) => `week ending ${w.week_ending}: ${w.received} received, ${w.resolved} resolved`).join('; ')}`}
                        series={[{ name: 'Received', values: weekly.map((w) => w.received), color: 'var(--s2)' },
                            { name: 'Resolved', values: weekly.map((w) => w.resolved), color: 'var(--s1)' }]} />
                </section>
                <section className="pd-panel pd-pad" aria-labelledby="pd-rt-h">
                    <SectionHead id="pd-rt-h" title="Resolution trend" sub="Share of each week's grievances resolved · dashed line is your portfolio"
                        right={<Legend items={[{ label: clientLabel, color: 'var(--s1)', line: true }, { label: 'Portfolio', color: 'var(--faint)', line: true }]} />} />
                    <LineChart labels={labels} width={580} height={280} yMax={1} yFmt={(v) => `${Math.round(v * 100)}%`}
                        ariaLabel={`Weekly resolution rate. ${weekly.map((w, i) => `week ending ${w.week_ending}: ${rateSeries[i] === null ? 'no grievances' : `${Math.round(rateSeries[i] * 100)}%`}`).join('; ')}`}
                        series={[{ name: clientLabel, values: rateSeries, color: 'var(--s1)', width: 2.4 },
                            ...(bench ? [{ name: 'Portfolio', values: benchRate, color: 'var(--faint)', dash: true, width: 1.6 }] : [])]} />
                </section>
            </div>

            <div className="pd-grid pd-g11 pd-mt">
                <section className="pd-panel pd-pad" aria-labelledby="pd-cat-h">
                    <SectionHead id="pd-cat-h" title="Top issue categories" sub={`Share of ${fmtCount(s.total)} grievances received`} />
                    <RankedBars items={categories} total={s.total} empty="No grievances in this period." />
                </section>
                <section className="pd-panel pd-pad" aria-labelledby="pd-loc-h">
                    <SectionHead id="pd-loc-h" title="Where complaints come from" sub={`Share of ${fmtCount(s.total)} grievances received`} />
                    <RankedBars items={places} total={s.total} empty="No grievances in this period." />
                </section>
            </div>

            {bench && bench.clients > 1 ? (
                <section className="pd-panel pd-pad pd-mt" aria-labelledby="pd-cmp-h">
                    <SectionHead id="pd-cmp-h" title="Against your portfolio" sub={`${clientLabel} compared with all ${bench.clients} active clients, last ${days} days`} />
                    <div className="pd-kv c3">
                        {compare.map((c) => {
                            const known = c.v !== null && c.v !== undefined && c.p !== null && c.p !== undefined;
                            const worse = known && (c.better === 'up' ? c.v < c.p : c.v > c.p);
                            return [
                                <div key={`${c.label}-l`}>{c.label}</div>,
                                <div key={`${c.label}-v`} className="v" style={worse ? { color: 'var(--crit)' } : undefined}>{c.f(c.v)}</div>,
                                <div key={`${c.label}-p`} className="muted" style={{ textAlign: 'right' }}>portfolio {c.f(c.p)}</div>,
                            ];
                        })}
                    </div>
                </section>
            ) : null}
        </div>
    );
}
