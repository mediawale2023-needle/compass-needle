/**
 * Navigation signals: counts shown beside sidebar destinations. Derived only
 * from /api/admin/alerts; a destination with no matching alerts shows nothing.
 */
import { highestSeverity, severityFromAlert } from './severity';

const DESTINATION_FOR_TYPE = [
    [(type) => type === 'setup_incomplete', 'onboarding'],
    [(type) => type.startsWith('whatsapp_'), 'messaging'],
    [(type) => type.startsWith('job_') || type === 'tenant_inactive', 'system'],
    [(type) => type === 'low_completeness', 'accounts'],
    [(type) => type === 'expiring_announcement', 'audit'],
];

export function destinationForAlert(alert) {
    const type = String(alert?.type || '');
    return DESTINATION_FOR_TYPE.find(([test]) => test(type))?.[1] || null;
}

/**
 * { [navId]: { count, severity } }. Command Centre carries the total of
 * alerts that need action (critical + warning), since it is the triage home.
 */
export function navSignals(alerts) {
    if (!Array.isArray(alerts)) return {};
    const buckets = {};
    const add = (id, severity) => {
        if (!buckets[id]) buckets[id] = { count: 0, severities: [] };
        buckets[id].count += 1;
        buckets[id].severities.push(severity);
    };
    for (const alert of alerts) {
        const severity = severityFromAlert(alert);
        const destination = destinationForAlert(alert);
        if (destination) add(destination, severity);
        if (severity === 'critical' || severity === 'warning') add('command', severity);
    }
    const result = {};
    for (const [id, bucket] of Object.entries(buckets)) {
        result[id] = { count: bucket.count, severity: highestSeverity(bucket.severities) };
    }
    return result;
}

/**
 * Platform condition summary for the sidebar footer card.
 * Returns null while alerts are unknown so the UI never claims "healthy"
 * without evidence.
 */
export function platformCondition(alerts) {
    if (!Array.isArray(alerts)) return null;
    const platformAlerts = alerts.filter((alert) => {
        const destination = destinationForAlert(alert);
        return destination === 'messaging' || destination === 'system';
    });
    if (!platformAlerts.length) return { severity: 'ok', title: 'No platform alerts', detail: null };
    const severity = highestSeverity(platformAlerts.map(severityFromAlert));
    const lead = platformAlerts.find((alert) => severityFromAlert(alert) === severity) || platformAlerts[0];
    return {
        severity,
        title: platformAlerts.length === 1 ? '1 platform alert' : `${platformAlerts.length} platform alerts`,
        detail: lead.title || null,
    };
}

/** Where an alert should take the operator; mirrors the Command Centre routing. */
export function alertDestination(alert) {
    const query = alert?.tenant_id ? `?tenant_id=${encodeURIComponent(alert.tenant_id)}` : '';
    const type = String(alert?.type || '');
    if (type === 'setup_incomplete' && alert.tenant_id) return `/dashboard/mps/${alert.tenant_id}/setup`;
    if (type === 'low_completeness') return `/dashboard/accounts${query}`;
    if (type === 'tenant_inactive') return `/dashboard/system/health${query}`;
    if (type.startsWith('whatsapp_inbound')) return '/dashboard/system/whatsapp-inbound';
    if (type === 'whatsapp_health') return '/dashboard/system/whatsapp';
    if (type.startsWith('job_')) return '/dashboard/system/jobs';
    if (type === 'expiring_announcement') return '/dashboard/system/announcements';
    return alert?.tenant_id ? `/dashboard/mps/${alert.tenant_id}` : '/dashboard/system/health';
}
