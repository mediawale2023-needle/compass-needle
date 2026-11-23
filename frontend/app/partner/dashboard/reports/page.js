'use client';

import Link from 'next/link';
import { HealthBadge } from '@/components/partner/ClientTable';
import { usePortfolio } from '@/components/partner/usePortfolio';
import { ErrorState, Icon, Skel, useCrumbs } from '@/components/partner/ui';
import { SEAT_LABEL } from '@/lib/partnerFormat';

export default function PartnerReportsPage() {
    const { ready, token, data, status, error, load } = usePortfolio(30);
    useCrumbs([{ label: 'Overview', href: '/partner/dashboard' }, { label: 'Reports' }]);
    if (!ready || !token) return null;
    const clients = data?.clients || [];

    return (
        <div>
            <div className="pd-pagehead">
                <div>
                    <div className="pd-eyebrow">Portfolio</div>
                    <h1 className="pd-title">Reports</h1>
                    <p className="pd-lede">
                        A branded report for each client, under your organisation&apos;s name. Reports carry aggregate figures only
                        and are generated on demand for the last 7, 30 or 90 days.
                    </p>
                </div>
            </div>
            {status === 'error' && <ErrorState title="Client data is unavailable right now." message={error} onRetry={load} />}
            {status === 'loading' && !data && <Skel h={320} />}
            {data && status !== 'error' && (
                <section className="pd-panel" aria-label="Client reports">
                    <div className="pd-tablewrap">
                        <table className="pd-table">
                            <thead><tr><th>Client</th><th>Status</th><th className="r"><span className="sr">Report</span></th></tr></thead>
                            <tbody>
                                {clients.map((c) => (
                                    <tr key={c.id}>
                                        <td><div className="pd-cname">{c.client_label}</div><div className="pd-csub">{[c.constituency, SEAT_LABEL[c.seat_type] || 'MP'].filter(Boolean).join(' · ')}</div></td>
                                        <td><HealthBadge client={c} /></td>
                                        <td className="r">
                                            {c.status === 'active' ? (
                                                <Link className="pd-btn sm" href={`/partner/dashboard/clients/${c.id}?tab=reports`} aria-label={`Report for ${c.client_label}`}>
                                                    <Icon name="report" size={15} /> Prepare report
                                                </Link>
                                            ) : <span className="pd-csub">Paused</span>}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {clients.length === 0 ? <div className="pd-empty">No clients yet.</div> : null}
                    </div>
                </section>
            )}
        </div>
    );
}
