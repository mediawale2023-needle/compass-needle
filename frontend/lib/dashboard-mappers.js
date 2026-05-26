const EMPTY_SUMMARY = {
    category_breakdown: {},
    status_breakdown: {},
    red_zones: [],
    critical_count: 0,
};

export function normalizeDashboardSummary(summary) {
    if (!summary || typeof summary !== 'object') return EMPTY_SUMMARY;
    return {
        category_breakdown: summary.category_breakdown || {},
        status_breakdown: summary.status_breakdown || {},
        red_zones: summary.red_zones || [],
        critical_count: summary.critical_count ?? 0,
    };
}

export function normalizeDashboardCases(response) {
    if (!response || typeof response !== 'object') return [];
    return response.cases || response.items || [];
}

export function normalizeDashboardLetters(response) {
    if (!response || typeof response !== 'object') return [];
    return response.items || response.letters || [];
}

export function normalizeDashboardNews(response) {
    if (!response || typeof response !== 'object') return [];
    return response.articles || [];
}

export function getDashboardTotalCases(summary) {
    const statuses = summary?.status_breakdown || {};
    return Object.values(statuses).reduce((sum, count) => sum + count, 0);
}

export function getDashboardIsEmpty(summary, cases) {
    return getDashboardTotalCases(summary) === 0 && (cases?.length || 0) === 0;
}

export function getEmptyDashboardSummary() {
    return { ...EMPTY_SUMMARY };
}
