/**
 * Severity vocabulary shared by every Admin surface.
 *
 * critical — act now; warning — act today; review — a decision is needed;
 * notice — Needle is handling it, shown for awareness; ok — healthy.
 * Alert severities from /api/admin/alerts map onto this scale exactly as the
 * Command Centre already labelled them (critical and error → Critical).
 */
export const SEVERITY_ORDER = ['critical', 'warning', 'review', 'notice', 'ok', 'neutral'];

export const SEVERITY_LABEL = {
    critical: 'Critical',
    warning: 'Warning',
    review: 'Review',
    notice: 'Notice',
    ok: 'Healthy',
    neutral: 'Unknown',
};

export function severityFromAlert(alert) {
    const raw = String(alert?.severity || '').toLowerCase();
    if (raw === 'critical' || raw === 'error') return 'critical';
    if (raw === 'warning') return 'warning';
    return 'review';
}

/** Backend health colours ('red' | 'amber' | 'green') → severity. */
export function severityFromHealthStatus(status) {
    if (status === 'red') return 'critical';
    if (status === 'amber') return 'warning';
    if (status === 'green') return 'ok';
    return 'neutral';
}

export function severityRank(severity) {
    const index = SEVERITY_ORDER.indexOf(severity);
    return index === -1 ? SEVERITY_ORDER.length : index;
}

export function compareSeverity(a, b) {
    return severityRank(a) - severityRank(b);
}

/** Most severe level in a list; 'ok' when the list is empty. */
export function highestSeverity(levels) {
    return [...levels].sort(compareSeverity)[0] || 'ok';
}

export function countAlertsBySeverity(alerts = []) {
    const counts = { critical: 0, warning: 0, review: 0, total: 0 };
    for (const alert of alerts) {
        counts[severityFromAlert(alert)] += 1;
        counts.total += 1;
    }
    return counts;
}

/** Alerts ordered most severe first, preserving backend order within a level. */
export function sortAlertsBySeverity(alerts = []) {
    return alerts
        .map((alert, index) => ({ alert, index }))
        .sort((a, b) => compareSeverity(severityFromAlert(a.alert), severityFromAlert(b.alert)) || a.index - b.index)
        .map(({ alert }) => alert);
}
