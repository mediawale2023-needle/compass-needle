'use client';

import { useState } from 'react';
import ClientTable from '@/components/partner/ClientTable';
import { Updated, usePortfolio } from '@/components/partner/usePortfolio';
import { ErrorState, PeriodSelect, Skel, useCrumbs } from '@/components/partner/ui';

export default function PartnerClientsPage() {
    const [days, setDays] = useState(30);
    const { ready, token, data, status, error, load, loadedAt } = usePortfolio(days);
    useCrumbs([{ label: 'Overview', href: '/partner/dashboard' }, { label: 'Clients' }]);
    if (!ready || !token) return null;

    return (
        <div>
            <div className="pd-pagehead">
                <div>
                    <div className="pd-eyebrow">Portfolio · last {days} days</div>
                    <h1 className="pd-title">Clients</h1>
                    <p className="pd-lede">
                        Every client constituency your organisation manages. Only aggregate figures are shown here; individual
                        grievances and citizen details stay with each office.
                    </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
                    <Updated at={status === 'ready' ? loadedAt : null} />
                    <PeriodSelect days={days} onChange={setDays} />
                </div>
            </div>
            {status === 'error' && <ErrorState title="Client data is unavailable right now." message={error} onRetry={load} />}
            {status === 'loading' && !data && <Skel h={420} />}
            {data && status !== 'error' && <ClientTable clients={data.clients} days={days} title="All clients" />}
        </div>
    );
}
