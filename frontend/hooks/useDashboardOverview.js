'use client';

import { useEffect, useState } from 'react';
import { apiGet } from '@/lib/api';
import {
    getDashboardIsEmpty,
    getEmptyDashboardSummary,
    normalizeDashboardCases,
    normalizeDashboardLetters,
    normalizeDashboardNewsFeeds,
    normalizeDashboardSummary,
} from '@/lib/dashboard-mappers';

export function useDashboardOverview() {
    const [summary, setSummary] = useState(null);
    const [cases, setCases] = useState([]);
    const [letters, setLetters] = useState([]);
    const [news, setNews] = useState({ national: [], local: [] });
    const [seatManifest, setSeatManifest] = useState(null);
    const [summaryLoaded, setSummaryLoaded] = useState(false);
    const [casesLoaded, setCasesLoaded] = useState(false);

    useEffect(() => {
        let cancelled = false;

        (async () => {
            const response = await apiGet('/api/dashboard/summary').catch(() => getEmptyDashboardSummary());
            if (!cancelled) {
                setSummary(normalizeDashboardSummary(response));
                setSummaryLoaded(true);
            }
        })();

        (async () => {
            const response = await apiGet('/api/cases?page=1&limit=20').catch(() => ({ cases: [] }));
            if (!cancelled) {
                setCases(normalizeDashboardCases(response));
                setCasesLoaded(true);
            }
        })();

        (async () => {
            const response = await apiGet('/api/maps/seat-manifest').catch(() => null);
            if (!cancelled) {
                setSeatManifest(response);
            }
        })();

        const timer = setTimeout(async () => {
            const [letterboxResponse, newsResponse] = await Promise.all([
                apiGet('/api/letterbox?direction=inbox&limit=10').catch(() => ({ items: [] })),
                Promise.all([
                    apiGet('/api/news?news_type=national').catch(() => ({ articles: [] })),
                    apiGet('/api/news?news_type=local').catch(() => ({ articles: [] })),
                ]),
            ]);

            if (!cancelled) {
                setLetters(normalizeDashboardLetters(letterboxResponse));
                setNews(normalizeDashboardNewsFeeds(newsResponse[0], newsResponse[1]));
            }
        }, 600);

        return () => {
            cancelled = true;
            clearTimeout(timer);
        };
    }, []);

    return {
        summary,
        cases,
        letters,
        news,
        seatManifest,
        isInitialLoading: !summaryLoaded || !casesLoaded,
        isEmpty: getDashboardIsEmpty(summary, cases),
    };
}
