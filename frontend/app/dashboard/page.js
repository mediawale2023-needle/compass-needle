'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
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
import { canAccessSansadAI } from '@/lib/account';

const MONO = dashboardFonts.mono;
const SANS = dashboardFonts.sans;
const MIN_DESKTOP_QUEUE_HEIGHT = 430;

// ─── Main Dashboard ────────────────────────────────────────────
export default function DashboardPage() {
    const { user } = useAuth();
    const router = useRouter();
    const canUseSansadAI = canAccessSansadAI(user);
    const { summary, cases, letters, news, seatManifest, isInitialLoading, isEmpty } = useDashboardOverview();
    const queueRef = useRef(null);
    const [desktopQueueHeight, setDesktopQueueHeight] = useState(null);

    const handleCaseClick = useCallback((id) => {
        router.push(`/dashboard/sansadx?case_id=${id}`);
    }, [router]);

    useEffect(() => {
        if (typeof window === 'undefined') return undefined;

        const syncQueueHeight = () => {
            if (window.innerWidth < 1280) {
                setDesktopQueueHeight(null);
                return;
            }
            const nextHeight = queueRef.current?.getBoundingClientRect?.().height || null;
            setDesktopQueueHeight(nextHeight ? Math.max(Math.round(nextHeight), MIN_DESKTOP_QUEUE_HEIGHT) : MIN_DESKTOP_QUEUE_HEIGHT);
        };

        syncQueueHeight();

        const observer = typeof ResizeObserver !== 'undefined' && queueRef.current
            ? new ResizeObserver(syncQueueHeight)
            : null;
        if (observer && queueRef.current) {
            observer.observe(queueRef.current);
        }

        window.addEventListener('resize', syncQueueHeight);
        return () => {
            window.removeEventListener('resize', syncQueueHeight);
            observer?.disconnect();
        };
    }, [cases]);

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
        <div
            className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)] gap-3.5 md:gap-[14px]"
            style={{
                fontFamily: SANS,
                fontSize: 12.5,
                color: P.ink,
            }}
        >
            {/* Row 1: KPI tiles — full width */}
            <div className="xl:col-[1/-1]">
                <DashboardKpiTiles summary={summary} />
            </div>

            {/* Row 2 left: Grievance table */}
            <div ref={queueRef} className="min-w-0 self-start xl:min-h-[430px]">
                <DashboardGrievanceQueue cases={cases} onCaseClick={handleCaseClick} />
            </div>

            {/* Row 2 right: Workload + Constituency map */}
            <div
                className="grid grid-rows-2 gap-3.5 md:gap-[14px] min-w-0 self-start xl:self-stretch"
                style={desktopQueueHeight ? { height: `${desktopQueueHeight}px` } : undefined}
            >
                <DashboardWorkloadCard summary={summary} />
                <DashboardConstituencyMap summary={summary} user={user} mapManifest={seatManifest} compact />
            </div>

            {/* Row 3 left: Letters + Press */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3.5 md:gap-[14px] min-w-0">
                <DashboardLettersCard letters={letters} />
                <DashboardPressCard news={news} />
            </div>

            {/* Row 3 right: Schedule + Activity */}
            <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_1fr] gap-3.5 md:gap-[14px] min-w-0">
                <DashboardEngagementsCard />
                <DashboardActivityFeed cases={cases} letters={letters} />
            </div>
        </div>
    );
}
