'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePartnerSession } from '@/lib/partnerSession';
import { partnerClients } from '@/lib/partnerApi';
import { fmtTimeIST } from '@/lib/partnerFormat';

export function usePortfolio(period) {
    const router = useRouter();
    const { ready, token, mustChangePassword } = usePartnerSession();
    const [data, setData] = useState(null);
    const [status, setStatus] = useState('loading'); // loading | ready | error
    const [error, setError] = useState('');
    const [loadedAt, setLoadedAt] = useState(null);

    const load = useCallback(async () => {
        setStatus('loading');
        setError('');
        try {
            setData(await partnerClients(period));
            setLoadedAt(new Date());
            setStatus('ready');
        } catch (err) {
            if (err.status === 401) {
                router.replace('/partner');
                return;
            }
            setError(err.message || 'Client data could not be loaded.');
            setStatus('error');
        }
    }, [period, router]);

    useEffect(() => {
        if (!ready) return;
        if (!token || mustChangePassword) {
            router.replace('/partner');
            return;
        }
        load();
    }, [ready, token, mustChangePassword, load, router]);

    return { ready, token, data, status, error, load, loadedAt };
}

export function Updated({ at }) {
    if (!at) return null;
    return <span className="pd-fresh"><span className="pd-live" /> Updated {fmtTimeIST(at)}</span>;
}
