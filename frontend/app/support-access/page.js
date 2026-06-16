'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { API_BASE } from '@/lib/api';
import { useAuth } from '@/lib/auth';

function SupportAccessInner() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { establishSession } = useAuth();
    const [state, setState] = useState({ loading: true, error: '' });

    useEffect(() => {
        let cancelled = false;

        async function consume() {
            const requestKey = searchParams.get('request');
            const launchToken = searchParams.get('launch_token');
            if (!requestKey || !launchToken) {
                if (!cancelled) {
                    setState({ loading: false, error: 'Support link is incomplete.' });
                }
                return;
            }

            try {
                const res = await fetch(`${API_BASE}/api/support-access/consume`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        request_key: requestKey,
                        launch_token: launchToken,
                    }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    throw new Error(data?.detail || 'Support session could not be opened.');
                }
                establishSession(data.user, data.token, false);
                router.replace('/dashboard');
            } catch (error) {
                if (!cancelled) {
                    setState({
                        loading: false,
                        error: error?.message || 'Support session could not be opened.',
                    });
                }
            }
        }

        consume();
        return () => { cancelled = true; };
    }, [searchParams, router, establishSession]);

    return (
        <div className="min-h-screen flex items-center justify-center px-6" style={{ background: '#F2EBD9' }}>
            <div className="glass-panel" style={{ width: '100%', maxWidth: 520, padding: '28px 24px' }}>
                <div style={{ fontSize: '0.72rem', letterSpacing: '0.14em', textTransform: 'uppercase', color: '#6b7f76', marginBottom: 10 }}>
                    Support Access
                </div>
                <h1 style={{ margin: 0, fontSize: '1.5rem', color: '#1a2e28' }}>
                    {state.loading ? 'Opening approved tenant session…' : 'Support session unavailable'}
                </h1>
                <p style={{ margin: '10px 0 0', color: '#4a5f58', lineHeight: 1.6 }}>
                    {state.loading
                        ? 'Please wait while Compass Needle verifies the tenant approval and starts a temporary view-only support session.'
                        : state.error}
                </p>
            </div>
        </div>
    );
}

export default function SupportAccessPage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen flex items-center justify-center px-6" style={{ background: '#F2EBD9' }}>
                <div className="glass-panel" style={{ width: '100%', maxWidth: 520, padding: '28px 24px' }}>
                    <div style={{ fontSize: '0.72rem', letterSpacing: '0.14em', textTransform: 'uppercase', color: '#6b7f76', marginBottom: 10 }}>
                        Support Access
                    </div>
                    <h1 style={{ margin: 0, fontSize: '1.5rem', color: '#1a2e28' }}>
                        Opening approved tenant session…
                    </h1>
                </div>
            </div>
        }>
            <SupportAccessInner />
        </Suspense>
    );
}
