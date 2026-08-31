'use client';

import { useEffect, useMemo, useState } from 'react';
import { apiGet } from '@/lib/api';
import { getOverviewIsEmpty, mapOverviewResponse } from '@/lib/dashboard-mappers';

export function useDashboardOverview() {
    const [overview, setOverview] = useState(null);
    const [engagements, setEngagements] = useState({ items: [] });
    const [localNews, setLocalNews] = useState({ articles: [] });
    const [seatManifest, setSeatManifest] = useState(null);
    const [overviewLoaded, setOverviewLoaded] = useState(false);
    const [isError, setIsError] = useState(false);

    useEffect(() => {
        let cancelled = false;

        (async () => {
            const response = await apiGet('/api/dashboard/overview').catch(() => null);
            if (cancelled) return;
            if (response) {
                setOverview(response);
            } else {
                setIsError(true);
            }
            setOverviewLoaded(true);
        })();

        (async () => {
            const response = await apiGet('/api/dashboard/engagements').catch(() => ({ items: [] }));
            if (!cancelled) setEngagements(response || { items: [] });
        })();

        (async () => {
            const response = await apiGet('/api/maps/seat-manifest').catch(() => null);
            if (!cancelled) setSeatManifest(response);
        })();

        const timer = setTimeout(async () => {
            const response = await apiGet('/api/news?news_type=local').catch(() => ({ articles: [] }));
            if (!cancelled) setLocalNews(response || { articles: [] });
        }, 400);

        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, []);

    const data = useMemo(
        () => mapOverviewResponse(overview, engagements, localNews),
        [overview, engagements, localNews],
    );

    return {
        data,
        overview,
        seatManifest,
        isInitialLoading: !overviewLoaded,
        isEmpty: overviewLoaded && !isError && getOverviewIsEmpty(overview),
        isError,
    };
}
