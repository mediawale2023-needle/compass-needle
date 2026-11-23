'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { usePartnerSession } from '@/lib/partnerSession';
import { partnerClientSummary } from '@/lib/partnerApi';
import { SEAT_LABEL, fmtTimeIST } from '@/lib/partnerFormat';
import { HealthBadge } from '@/components/partner/ClientTable';
import ClientSwitcher from '@/components/partner/ClientSwitcher';
import PartnerAnalytics from '@/components/partner/PartnerAnalytics';
import PartnerOverview from '@/components/partner/PartnerOverview';
import ReportPanel from '@/components/partner/ReportPanel';
import { ErrorState, Icon, PeriodSelect, Skel, useCrumbs } from '@/components/partner/ui';

const TABS = [['overview', 'Overview'], ['analytics', 'Analytics'], ['reports', 'Reports']];

export default function PartnerClientPage() {
    const router = useRouter();
    const params = useParams();
    const seatId = params?.seatId;
    const { ready, token, partner, mustChangePassword } = usePartnerSession();
    const [tab, setTab] = useState('overview');
    const [days, setDays] = useState(30);
    const [result, setResult] = useState(null);
    const [status, setStatus] = useState('loading'); // loading | ready | error | missing
    const [error, setError] = useState('');
    const [loadedAt, setLoadedAt] = useState(null);

    const load = useCallback(async () => {
        setStatus('loading');
        setError('');
        try {
            setResult(await partnerClientSummary(seatId, days));
            setLoadedAt(new Date());
            setStatus('ready');
        } catch (err) {
            if (err.status === 401) return router.replace('/partner');
            if (err.status === 404 || err.status === 409) {
                setError(err.message);
                setStatus('missing');
                return;
            }
            setError(err.message || 'Client data could not be loaded.');
            setStatus('error');
        }
    }, [seatId, days, router]);

    useEffect(() => {
        if (!ready) return;
        if (!token || mustChangePassword) {
            router.replace('/partner');
            return;
        }
        load();
    }, [ready, token, mustChangePassword, load, router]);

    // Deep link from the Reports page: /partner/dashboard/clients/7?tab=reports
    useEffect(() => {
        const wanted = new URLSearchParams(window.location.search).get('tab');
        if (TABS.some(([k]) => k === wanted)) setTab(wanted);
    }, []);

    const signOutRedirect = useCallback(() => router.replace('/partner'), [router]);
    const client = result?.client;
    useCrumbs([{ label: 'Clients', href: '/partner/dashboard/clients' }, { label: client?.client_label || 'Client' }]);

    if (!ready || !token) return null;
    const s = result?.summary;

    return (
        <div>
            {status === 'missing' && (
                <div role="alert" className="pd-panel pd-pad">
                    <h1 className="pd-title" style={{ fontSize: 26 }}>This client isn&apos;t available</h1>
                    <p className="muted" style={{ margin: '0 0 14px' }}>{error}</p>
                    <Link className="pd-link" href="/partner/dashboard/clients">← Back to clients</Link>
                </div>
            )}

            {status === 'error' && <ErrorState title="Client data is unavailable right now." message={error} onRetry={load} />}

            {status === 'loading' && !result && (
                <div aria-busy="true" aria-label="Loading client" style={{ display: 'grid', gap: 20 }}>
                    <Skel h={64} w={360} /><Skel h={112} /><Skel h={240} />
                </div>
            )}

            {result && status !== 'missing' && status !== 'error' && (
                <>
                    <div className="pd-chead">
                        <div className="pd-cid">
                            <div className="pd-cmono" aria-hidden="true">{(client.client_label || '?').slice(0, 1).toUpperCase()}</div>
                            <div style={{ minWidth: 0 }}>
                                <div className="pd-eyebrow">{client.seat_type === 'mla' ? 'Vidhan Sabha client' : 'Lok Sabha client'}</div>
                                <h1 className="pd-title" style={{ margin: '4px 0 6px' }}>{client.client_label}</h1>
                                <div className="pd-cmeta">
                                    {client.constituency ? <><span>{client.constituency}</span><span className="sep">|</span></> : null}
                                    <span>{SEAT_LABEL[client.seat_type] || 'MP'}</span><span className="sep">|</span>
                                    <HealthBadge client={{ ...client, summary: s }} />
                                    {loadedAt ? <><span className="sep">|</span><span className="pd-fresh"><span className="pd-live" /> Updated {fmtTimeIST(loadedAt)}</span></> : null}
                                </div>
                            </div>
                        </div>
                        <div className="actions" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <ClientSwitcher currentId={seatId} />
                            <button type="button" className="pd-btn primary" onClick={() => setTab('reports')}><Icon name="report" size={16} /> Client report</button>
                        </div>
                    </div>

                    <div role="tablist" aria-label="Client views" className="pd-tabs">
                        {TABS.map(([key, label]) => (
                            <button key={key} type="button" role="tab" id={`tab-${key}`} aria-selected={tab === key} aria-controls={`panel-${key}`} onClick={() => setTab(key)}>{label}</button>
                        ))}
                    </div>

                    {tab === 'overview' && (
                        <div role="tabpanel" id="panel-overview" aria-labelledby="tab-overview">
                            <PartnerOverview seatId={seatId} summary={s} days={days} onUnauthorized={signOutRedirect} />
                        </div>
                    )}
                    {tab === 'analytics' && (
                        <div role="tabpanel" id="panel-analytics" aria-labelledby="tab-analytics">
                            <PartnerAnalytics summary={s} days={days} onDaysChange={setDays} clientLabel={client.client_label} />
                        </div>
                    )}
                    {tab === 'reports' && (
                        <div role="tabpanel" id="panel-reports" aria-labelledby="tab-reports">
                            <div className="pd-pagehead" style={{ marginBottom: 18 }}>
                                <div><h2 className="pd-sec" style={{ fontSize: 17 }}>Reports</h2><div className="pd-secsub">The report uses the same figures as the Analytics tab for the chosen period.</div></div>
                                <PeriodSelect days={days} onChange={setDays} />
                            </div>
                            <ReportPanel seatId={seatId} days={days} clientLabel={client.client_label} partner={partner} />
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
