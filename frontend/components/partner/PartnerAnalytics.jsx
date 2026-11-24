'use client';

import { useEffect, useState } from 'react';
import { partnerClients } from '@/lib/partnerApi';
import { bucketName, fmtCount, fmtDays, fmtPct, periodKey, periodPhrase, windowLabel } from '@/lib/partnerFormat';
import { BarChart, Legend, LineChart, bucketLabel } from './charts';
import { Kpis, PeriodSelect, RankedBars, SectionHead } from './ui';

/** Portfolio averages for comparison, from the same aggregate /clients endpoint the portfolio page uses. */
function usePortfolioBenchmark(period) {
    const [bench, setBench] = useState(null);
    useEffect(() => {
        let cancelled = false;
        setBench(null);
        partnerClients(period).then((d) => {
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
                trend: p.trend || [],
                bucketDays: p.bucket_days,
            });
        }).catch(() => { if (!cancelled) setBench(null); });
        return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [periodKey(period)]);
    return bench;
}

export default function PartnerAnalytics({ summary: s, period, onPeriodChange, clientLabel }) {
    const bench = usePortfolioBenchmark(period);
    const trend = s.trend || [];
    const unit = bucketName(s.bucket_days || 7);
    const labels = trend.map((w) => bucketLabel(w, s.bucket_days || 7));
    const rateSeries = trend.map((w) => (w.received ? w.resolved / w.received : null));
    // Portfolio buckets line up with this client's only when both use the same bucket size (same span).
    const benchByEnd = bench && bench.bucketDays === s.bucket_days ? Object.fromEntries(bench.trend.map((w) => [w.period_end, w])) : {};
    const benchRate = trend.map((w) => {
        const b = benchByEnd[w.period_end];
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
                    <div className="pd-secsub">{windowLabel(s.window, period)} · charts group grievances by {unit}</div>
                </div>
                <PeriodSelect period={period} onChange={onPeriodChange} />
            </div>

            <Kpis label={`Headline numbers, ${periodPhrase(period)}`} items={[
                { label: 'Received', value: fmtCount(s.total) },
                { label: 'Resolved', value: fmtPct(s.resolution_rate), foot: `${fmtCount(s.resolved)} grievances` },
                { label: 'Still open', value: fmtCount(s.open) },
                { label: 'Critical', value: fmtCount(s.critical), tone: s.critical >= 5 ? 'crit' : undefined },
                { label: 'Avg. to resolve', value: fmtDays(s.avg_resolution_days) },
            ]} />

            <div className="pd-grid pd-g11 pd-mt">
                <section className="pd-panel pd-pad" aria-labelledby="pd-vol-h">
                    <SectionHead id="pd-vol-h" title="Grievance volume" sub={`Received and resolved, by ${unit}`}
                        right={<Legend items={[{ label: 'Received', color: 'var(--s2)' }, { label: 'Resolved', color: 'var(--s1)' }]} />} />
                    <BarChart labels={labels} width={580} height={280}
                        ariaLabel={`Grievances by ${unit}, ${periodPhrase(period)}. ${trend.map((w) => `${w.period_start} to ${w.period_end}: ${w.received} received, ${w.resolved} resolved`).join('; ')}`}
                        series={[{ name: 'Received', values: trend.map((w) => w.received), color: 'var(--s2)' },
                            { name: 'Resolved', values: trend.map((w) => w.resolved), color: 'var(--s1)' }]} />
                </section>
                <section className="pd-panel pd-pad" aria-labelledby="pd-rt-h">
                    <SectionHead id="pd-rt-h" title="Resolution trend" sub={`Share of each ${unit}'s grievances resolved${benchRate.some((v) => v !== null) ? ' · dashed line is your portfolio' : ''}`}
                        right={<Legend items={[{ label: clientLabel, color: 'var(--s1)', line: true }, ...(benchRate.some((v) => v !== null) ? [{ label: 'Portfolio', color: 'var(--faint)', line: true }] : [])]} />} />
                    <LineChart labels={labels} width={580} height={280} yMax={1} yFmt={(v) => `${Math.round(v * 100)}%`}
                        ariaLabel={`Resolution rate by ${unit}. ${trend.map((w, i) => `${w.period_start} to ${w.period_end}: ${rateSeries[i] === null ? 'no grievances' : `${Math.round(rateSeries[i] * 100)}%`}`).join('; ')}`}
                        series={[{ name: clientLabel, values: rateSeries, color: 'var(--s1)', width: 2.4 },
                            ...(benchRate.some((v) => v !== null) ? [{ name: 'Portfolio', values: benchRate, color: 'var(--faint)', dash: true, width: 1.6 }] : [])]} />
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
                    <SectionHead id="pd-cmp-h" title="Against your portfolio" sub={`${clientLabel} compared with all ${bench.clients} active clients, ${periodPhrase(period)}`} />
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
