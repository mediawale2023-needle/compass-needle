'use client';

import { useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import DashboardActivityFeed from '@/components/dashboard/DashboardActivityFeed';
import DashboardConstituencyMap from '@/components/dashboard/DashboardConstituencyMap';
import DashboardEmptyState from '@/components/dashboard/DashboardEmptyState';
import DashboardEngagementsCard from '@/components/dashboard/DashboardEngagementsCard';
import DashboardGrievanceQueue from '@/components/dashboard/DashboardGrievanceQueue';
import DashboardKpiTiles from '@/components/dashboard/DashboardKpiTiles';
import DashboardLettersCard from '@/components/dashboard/DashboardLettersCard';
import DashboardPressCard from '@/components/dashboard/DashboardPressCard';
import DashboardWorkloadCard from '@/components/dashboard/DashboardWorkloadCard';
import { dashboardFonts, dashboardPalette as P } from '@/lib/dashboard-theme';
import { useDashboardOverview } from '@/hooks/useDashboardOverview';

const MONO = dashboardFonts.mono;
const SANS = dashboardFonts.sans;

// ─── Main Dashboard ────────────────────────────────────────────
export default function DashboardPage() {
    const { user } = useAuth();
    const router = useRouter();
    const canUseSansadAI = user?.role === 'mp' || user?.role === 'admin';
    const { summary, cases, letters, news, isInitialLoading, isEmpty } = useDashboardOverview();

    const handleCaseClick = useCallback((id) => {
        router.push(`/dashboard/sansadx?case_id=${id}`);
    }, [router]);

    if (isInitialLoading) {
        return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
                <div style={{ fontFamily: MONO, fontSize: 11, letterSpacing: '0.14em', color: P.ink3, textTransform: 'uppercase' }}>
                    Loading…
                </div>
            </div>
        );
    }

    if (isEmpty) {
        return <DashboardEmptyState canUseSansadAI={canUseSansadAI} />;
    }

    return (
        <div style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1.55fr) minmax(0, 1fr)',
            gridTemplateRows: 'auto minmax(0,auto) minmax(0,auto)',
            gap: 14,
            fontFamily: SANS,
            fontSize: 12.5,
            color: P.ink,
        }}>
            {/* Row 1: KPI tiles — full width */}
            <div style={{ gridColumn: '1 / -1' }}>
                <DashboardKpiTiles summary={summary} />
            </div>

            {/* Row 2 left: Grievance table */}
            <DashboardGrievanceQueue cases={cases} onCaseClick={handleCaseClick} />

            {/* Row 2 right: Workload + Engagements */}
            <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', gap: 14 }}>
                <DashboardWorkloadCard summary={summary} />
                <DashboardEngagementsCard />
            </div>

            {/* Row 3 left: Letters + Press */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <DashboardLettersCard letters={letters} />
                <DashboardPressCard news={news} />
            </div>

            {/* Row 3 right: Map + Activity */}
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 14 }}>
                <DashboardConstituencyMap summary={summary} user={user} />
                <DashboardActivityFeed cases={cases} letters={letters} />
            </div>
        </div>
    );
}
