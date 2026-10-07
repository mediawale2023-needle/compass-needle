/**
 * Needs Attention queue — one deterministic definition used by the Command
 * Centre (and later Account 360).
 *
 * Sources are real: /api/admin/alerts, plus /api/admin/system-health for
 * WhatsApp. When system-health is available the generic `whatsapp_health`
 * alert is replaced by the precise incidents from deriveWhatsAppIncidents()
 * (global token → ONE platform incident; routing gaps → account incidents),
 * so the same problem is never listed twice.
 *
 * Ranking: severity → scope (platform before account) → impact rank of the
 * alert type → backend order. Alerts carry no timestamps, so age is not used
 * and never displayed.
 */
import { alertDestination } from './signals';
import { compareSeverity, severityFromAlert } from './severity';
import { deriveWhatsAppIncidents } from './whatsapp';

// Lower = more operational impact. Unknown types sort after known ones.
const IMPACT_RANK = {
    meta_token_invalid: 0,
    routing_unavailable: 1,
    outbound_failures: 2,
    inbound_processing: 3,
    whatsapp_health: 4,
    whatsapp_inbound_failed: 5,
    whatsapp_inbound_stale_processing: 6,
    whatsapp_inbound_stale_received: 7,
    routing_config: 8,
    job_failed: 9,
    job_stuck: 10,
    tenant_inactive: 11,
    setup_incomplete: 12,
    low_completeness: 13,
    expiring_announcement: 14,
};

const ACTION_LABEL = {
    whatsapp_health: 'Open Messaging',
    whatsapp_inbound_failed: 'Open inbound',
    whatsapp_inbound_stale_processing: 'Open inbound',
    whatsapp_inbound_stale_received: 'Open inbound',
    job_failed: 'Open jobs',
    job_stuck: 'Open jobs',
    tenant_inactive: 'View account activity',
    setup_incomplete: 'Resume setup',
    low_completeness: 'Complete profile',
    expiring_announcement: 'Review announcement',
};

const ICON_KIND = {
    meta_token_invalid: 'messaging',
    routing_unavailable: 'messaging',
    routing_config: 'messaging',
    outbound_failures: 'messaging',
    inbound_processing: 'messaging',
    whatsapp_health: 'messaging',
    whatsapp_inbound_failed: 'messaging',
    whatsapp_inbound_stale_processing: 'messaging',
    whatsapp_inbound_stale_received: 'messaging',
    job_failed: 'job',
    job_stuck: 'job',
    tenant_inactive: 'activity',
    setup_incomplete: 'setup',
    low_completeness: 'setup',
    expiring_announcement: 'announcement',
};

function fromAlert(alert, index) {
    const type = String(alert.type || 'alert');
    const tenantId = alert.tenant_id ?? null;
    return {
        id: `alert-${type}-${tenantId ?? 'p'}-${index}`,
        kind: type,
        icon: ICON_KIND[type] || 'alert',
        severity: severityFromAlert(alert),
        title: alert.title || 'Alert',
        detail: alert.description || null,
        scope: tenantId !== null ? 'account' : 'platform',
        tenantId,
        action: { label: ACTION_LABEL[type] || 'Investigate', href: alertDestination(alert) },
        order: index,
    };
}

function fromIncident(incident, index) {
    return {
        id: `wa-${incident.id}`,
        kind: incident.kind,
        icon: ICON_KIND[incident.kind] || 'messaging',
        severity: incident.severity,
        title: incident.title,
        detail: incident.detail,
        scope: incident.scope,
        tenantId: incident.tenantId ?? null,
        affected: incident.affected || null,
        action: incident.action,
        order: 1000 + index,
    };
}

export function compareAttention(a, b) {
    return compareSeverity(a.severity, b.severity)
        || (a.scope === b.scope ? 0 : a.scope === 'platform' ? -1 : 1)
        || (IMPACT_RANK[a.kind] ?? 99) - (IMPACT_RANK[b.kind] ?? 99)
        || a.order - b.order;
}

/**
 * @param {object} input
 * @param {Array|null} input.alerts           /api/admin/alerts items (null = unavailable)
 * @param {object|null} [input.whatsapp]      system-health `whatsapp` block
 * @param {Map|object} [input.accounts]       tenant_id → { name, detail }
 */
export function buildAttentionItems({ alerts, whatsapp = null, accounts = {} }) {
    if (!Array.isArray(alerts)) return null;
    const lookup = accounts instanceof Map ? accounts : new Map(Object.entries(accounts || {}));
    const incidents = deriveWhatsAppIncidents(whatsapp);
    const replaceWhatsAppAlert = Boolean(whatsapp);

    const items = [
        ...alerts
            .filter((alert) => !(replaceWhatsAppAlert && alert.type === 'whatsapp_health'))
            .map(fromAlert),
        ...incidents.map(fromIncident),
    ];

    for (const item of items) {
        if (item.tenantId !== null && item.tenantId !== undefined) {
            const account = lookup.get(String(item.tenantId));
            item.account = account ? { name: account.name, detail: account.detail || null } : { name: `Account #${item.tenantId}`, detail: null };
        } else {
            item.account = null;
        }
    }
    return items.sort(compareAttention);
}

export function countAttention(items) {
    const counts = { critical: 0, warning: 0, review: 0, notice: 0, total: 0 };
    for (const item of items || []) {
        counts[item.severity] = (counts[item.severity] || 0) + 1;
        counts.total += 1;
    }
    return counts;
}
