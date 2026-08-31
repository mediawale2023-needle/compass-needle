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

export function normalizeDashboardNewsFeeds(nationalResponse, localResponse) {
    return {
        national: normalizeDashboardNews(nationalResponse),
        local: normalizeDashboardNews(localResponse),
    };
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

// ─── /api/dashboard/overview → locked Overview design props ───────────────

function mapOverviewQueueRow(row) {
    const raw = row && typeof row === 'object' ? row : {};
    const action = raw.action && typeof raw.action === 'object' && raw.action.label
        ? { label: raw.action.label, href: raw.action.href || null }
        : null;
    return {
        id: raw.case_ref || (raw.id != null ? `#${raw.id}` : ''),
        caseId: raw.id ?? null,
        meta: raw.meta || '',
        threadCount: raw.thread_count ?? 1,
        channel: raw.channel || '',
        message: raw.message || '',
        issue: raw.issue || '',
        location: raw.location || '',
        state: raw.state || '',
        needleStatus: raw.needle_status || '',
        govtStatus: raw.govt_status || '',
        assignedTo: raw.assigned_to || null,
        recency: raw.recency || '',
        action,
        critical: !!raw.critical,
    };
}

function mapOverviewGovt(govt) {
    const g = govt && typeof govt === 'object' ? govt : {};
    return {
        ready: g.ready ?? 0,
        registered: g.registered ?? 0,
        department: g.department ?? 0,
        resolved: g.resolved ?? 0,
        syncIssues: g.sync_issues ?? 0,
        issues: Array.isArray(g.issues) ? g.issues : [],
    };
}

function formatEngagementTime(entry) {
    if (!entry || typeof entry !== 'object') return '';
    if (entry.is_all_day) return 'All day';
    if (!entry.starts_at) return '';
    const parsed = new Date(entry.starts_at);
    if (Number.isNaN(parsed.getTime())) return '';
    return parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
}

function normalizeOverviewToday(engagements) {
    const items = engagements && Array.isArray(engagements.items) ? engagements.items : [];
    return items.map((entry) => ({
        time: formatEngagementTime(entry),
        item: entry.title || '',
    }));
}

function normalizeOverviewMedia(localNews) {
    const articles = localNews && Array.isArray(localNews.articles) ? localNews.articles : [];
    return articles.slice(0, 3).map((article) => ({
        source: article.source || 'Local desk',
        title: article.title || '',
        href: article.link || article.url || null,
    }));
}

export function mapOverviewResponse(overview, engagements, localNews) {
    const o = overview && typeof overview === 'object' ? overview : {};
    return {
        seat: o.seat || 'Constituency',
        dateLabel: o.date_label || 'Today',
        attention: Array.isArray(o.attention_counts)
            ? o.attention_counts.map((c) => ({
                key: c.key,
                label: c.label || '',
                value: c.value ?? 0,
                tone: c.tone || 'green',
            }))
            : [],
        queue: Array.isArray(o.attention_queue) ? o.attention_queue.map(mapOverviewQueueRow) : [],
        govt: mapOverviewGovt(o.government_tracking),
        hotspots: Array.isArray(o.constituency_pressure)
            ? o.constituency_pressure.map((h) => ({ name: h.name || '', count: h.count ?? 0 }))
            : [],
        issuePressure: Array.isArray(o.issue_pressure)
            ? o.issue_pressure.map((i) => ({
                title: i.title || '',
                place: i.place || '',
                count: i.count ?? 0,
            }))
            : [],
        today: normalizeOverviewToday(engagements),
        officePending: Array.isArray(o.office_pending)
            ? o.office_pending.map((p) => ({ key: p.key, label: p.label || '', href: p.href || null }))
            : [],
        movement: Array.isArray(o.recent_movement)
            ? o.recent_movement.map((m) => ({
                id: m.id ?? `${m.time}-${m.item}`,
                time: m.time || '',
                item: m.item || '',
                tone: m.tone || 'rust',
                href: m.href || null,
            }))
            : [],
        media: normalizeOverviewMedia(localNews),
    };
}

export function getOverviewIsEmpty(overview) {
    const o = overview && typeof overview === 'object' ? overview : null;
    if (!o) return false;
    const attn = Array.isArray(o.attention_counts)
        ? o.attention_counts.reduce((sum, c) => sum + (c.value || 0), 0)
        : 0;
    const queue = Array.isArray(o.attention_queue) ? o.attention_queue.length : 0;
    const gt = o.government_tracking || {};
    const gtTotal = (gt.ready || 0) + (gt.registered || 0) + (gt.department || 0)
        + (gt.resolved || 0) + (gt.sync_issues || 0);
    const threads = (o.validation && o.validation.thread_count) || 0;
    return attn === 0 && queue === 0 && gtTotal === 0 && threads === 0;
}
