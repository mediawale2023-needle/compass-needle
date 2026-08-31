'use client';

import { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import DashboardEmptyState from '@/components/dashboard/DashboardEmptyState';
import OverviewDashboard from '@/components/dashboard/OverviewDashboard';
import { useDashboardOverview } from '@/hooks/useDashboardOverview';
import { canAccessSansadAI } from '@/lib/account';

// ─── Overview ──────────────────────────────────────────────────
// Locked design (components/dashboard/OverviewDashboard) wired to the real
// tenant-scoped GET /api/dashboard/overview aggregate. Do not redesign.
export default function DashboardPage() {
    const { user } = useAuth();
    const router = useRouter();
    const canUseSansadAI = canAccessSansadAI(user);
    const { data, isInitialLoading, isEmpty } = useDashboardOverview();

    const handleNavigate = useCallback((href) => {
        if (typeof href === 'string' && href.length) {
            router.push(href);
        }
    }, [router]);

    if (isInitialLoading) {
        return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
                <div
                    style={{
                        fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
                        fontSize: 11,
                        letterSpacing: '0.14em',
                        color: '#837A69',
                        textTransform: 'uppercase',
                    }}
                >
                    Loading…
                </div>
            </div>
        );
    }

    if (isEmpty) {
        return <DashboardEmptyState canUseSansadAI={canUseSansadAI} />;
    }

    return <OverviewDashboard data={data} onNavigate={handleNavigate} />;
}
