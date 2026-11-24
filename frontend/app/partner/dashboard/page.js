'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Updated, usePortfolio } from '@/components/partner/usePortfolio';
import { DEFAULT_PERIOD, bucketName, clientHealth, fmtCount, healthReasons, periodPhrase, windowLabel } from '@/lib/partnerFormat';
import ClientTable from '@/components/partner/ClientTable';
import { LineChart, Legend, bucketLabel } from '@/components/partner/charts';
import { ErrorState, Icon, Kpis, PeriodSelect, SectionHead, Skel, useCrumbs } from '@/components/partner/ui';

export default function PartnerDashboardPage() {
    const [period, setPeriod] = useState(DEFAULT_PERIOD);
    const { ready, token, data, status, error, load, loadedAt } = usePortfolio(period);
    useCrumbs([{ label: 'Overview' }]);

    if (!ready || !token) return null;

    const clients = data?.clients || [];
    const live = clients.filter((c) => c.status === 'active');
    const attention = live.map((c) => ({ c, h: clientHealth(c) })).filter((x) => x.h.level !== 'ok')
        .sort((a, b) => b.h.rank - a.h.rank).slice(0, 5);
    const urgent = attention.filter((x) => x.h.level === 'attention').length;
    const p = data?.portfolio;
    const rate = p && p.total ? p.resolved / p.total : null;
    const trend = p?.trend || [];
    const bucketDays = p?.bucket_days || 7;

    return (
        <div>
            <div className="pd-pagehead">
                <div>
                    <div className="pd-eyebrow">Portfolio · {windowLabel(data?.window, period)}</div>
                    <h1 className="pd-title">Your clients</h1>
                    <p className="pd-lede">
                        {data ? (
                            <>
                                {live.length} active {live.length === 1 ? 'client' : 'clients'}.{' '}
                                {urgent ? <b>{urgent} {urgent === 1 ? 'needs' : 'need'} attention.</b> : 'None needs urgent attention.'}{' '}
                                Figures are aggregate counts only.
                            </>
                        ) : 'Loading clients…'}
                    </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
                    <Updated at={status === 'ready' ? loadedAt : null} />
                    <PeriodSelect period={period} onChange={setPeriod} />
                </div>
            </div>

            {status === 'error' && <ErrorState title="Client data is unavailable right now." message={error} onRetry={load} />}

            {status === 'loading' && !data && (
                <div aria-busy="true" aria-label="Loading clients" style={{ display: 'grid', gap: 20 }}>
                    <Skel h={112} /><div className="pd-grid pd-g21"><Skel h={320} /><Skel h={320} /></div><Skel h={280} />
                </div>
            )}

            {data && status !== 'error' && (clients.length === 0 ? (
                <div className="pd-panel pd-empty">
                    <h2 className="pd-sec" style={{ fontSize: 18 }}>No clients yet</h2>
                    <p style={{ maxWidth: 440, margin: '8px auto 0' }}>
                        Clients that Needle onboards for you appear here automatically, with their grievance numbers and your
                        branded report. There is nothing to request or approve.
                    </p>
                </div>
            ) : (
                <>
                    <Kpis label={`Portfolio totals, ${periodPhrase(period)}`} items={[
                        { label: 'Grievances received', value: fmtCount(p.total), foot: `Across ${live.length} active clients` },
                        { label: 'Resolved', value: fmtCount(p.resolved), foot: 'Of those received in the period' },
                        { label: 'Still open', value: fmtCount(p.open), foot: 'Received in the period, not yet resolved' },
                        { label: 'Resolution rate', value: rate === null ? '—' : (rate * 100).toFixed(1), unit: rate === null ? '' : '%', foot: `${fmtCount(p.critical)} critical` },
                    ]} />

                    <div className="pd-grid pd-g21 pd-mt">
                        <section className="pd-panel pd-pad" aria-labelledby="pd-trend-h">
                            <SectionHead id="pd-trend-h" title="Received and resolved" sub={`All active clients · by ${bucketName(bucketDays)}, ${periodPhrase(period)}`}
                                right={<Legend items={[{ label: 'Received', color: 'var(--s2)', line: true }, { label: 'Resolved', color: 'var(--s1)', line: true }]} />} />
                            {trend.length ? (
                                <LineChart ariaLabel={`Portfolio grievances by ${bucketName(bucketDays)}, ${periodPhrase(period)}. ${trend.map((w) => `${w.period_start} to ${w.period_end}: ${w.received} received, ${w.resolved} resolved`).join('; ')}`}
                                    labels={trend.map((w) => bucketLabel(w, bucketDays))} height={290}
                                    series={[{ name: 'Received', values: trend.map((w) => w.received), color: 'var(--s2)' },
                                        { name: 'Resolved', values: trend.map((w) => w.resolved), color: 'var(--s1)', width: 2.4 }]} />
                            ) : <p className="muted" style={{ fontSize: 13 }}>No figures for this period yet.</p>}
                            <p className="pd-note">Each point covers one {bucketName(bucketDays)} and ends on the date shown. The gap between the lines is backlog added in that {bucketName(bucketDays)}.</p>
                        </section>
                        <section className="pd-panel pd-first" aria-labelledby="pd-att-h">
                            <div style={{ padding: '18px 20px 6px' }}><SectionHead id="pd-att-h" title="Needs attention" sub="Ranked by critical threads and resolution rate" /></div>
                            {attention.length ? (
                                <ul className="pd-att">
                                    {attention.map(({ c, h }) => (
                                        <li key={c.id}>
                                            <Link className="row" href={`/partner/dashboard/clients/${c.id}`}>
                                                <span className={`pd-dot ${h.level === 'attention' ? 'crit' : 'warn'}`} aria-label={h.level === 'attention' ? 'Needs attention' : 'Watch'} />
                                                <div style={{ minWidth: 0 }}><div className="t">{c.client_label}</div><div className="d">{healthReasons(c)}</div></div>
                                                <div className={`n num ${h.level === 'attention' ? 'crit' : ''}`}>{c.summary.critical}<div className="d" style={{ margin: 0, fontWeight: 400, fontSize: 11.5 }}>critical</div></div>
                                                <span className="chev"><Icon name="chev" size={16} /></span>
                                            </Link>
                                        </li>
                                    ))}
                                </ul>
                            ) : <p className="muted" style={{ padding: '0 20px 20px', fontSize: 13 }}>No client needs attention in this period.</p>}
                        </section>
                    </div>

                    <div className="pd-mt"><ClientTable clients={clients} period={period} compact onSeeAll="/partner/dashboard/clients" /></div>
                </>
            ))}
        </div>
    );
}
