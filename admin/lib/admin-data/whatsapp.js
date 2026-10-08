/**
 * WhatsApp incident model — the real Needle model, not the mock-up's.
 *
 * Needle sends through ONE global Meta access token. Therefore:
 *   - an invalid/missing global token is a PLATFORM-wide incident;
 *   - incomplete per-tenant routing (number / phone-number ID) is an
 *     ACCOUNT-specific incident;
 *   - failed outbound sends for a tenant are an ACCOUNT delivery failure.
 * A per-number token failure cannot happen and is never produced here, and
 * no "reconnect number" action exists.
 *
 * Input shapes are the backend responses: /api/admin/system-health
 * (`whatsapp` key) and /api/admin/whatsapp/outbound (`items`).
 */
import { severityFromHealthStatus } from './severity';

const MESSAGING = '/dashboard/system/whatsapp';

export function deriveWhatsAppIncidents(whatsapp) {
    if (!whatsapp) return [];
    const incidents = [];
    const token = whatsapp.meta_token || {};
    const routing = whatsapp.routing || {};
    const outbound = whatsapp.outbound || {};
    const webhook = whatsapp.webhook || {};

    if (token.status === 'red') {
        incidents.push({
            id: 'meta-token',
            scope: 'platform',
            kind: 'meta_token_invalid',
            severity: 'critical',
            title: token.configured === false ? 'Meta access token missing' : 'Meta access token invalid',
            detail: token.detail || null,
            affected: 'All WhatsApp accounts',
            action: { label: 'Open Messaging', href: MESSAGING },
        });
    }

    if (routing.status === 'red') {
        incidents.push({
            id: 'routing-platform',
            scope: 'platform',
            kind: 'routing_unavailable',
            severity: 'critical',
            title: 'WhatsApp routing unavailable',
            detail: routing.detail || null,
            affected: 'All WhatsApp accounts',
            action: { label: 'Open routing', href: `${MESSAGING}#routing` },
        });
    }

    for (const issue of routing.tenant_issues || []) {
        incidents.push({
            id: `routing-${issue.tenant_id}`,
            scope: 'account',
            kind: 'routing_config',
            severity: 'warning',
            tenantId: issue.tenant_id,
            title: 'WhatsApp routing incomplete',
            detail: issue.issue || null,
            affected: [issue.name, issue.constituency].filter(Boolean).join(' · ') || null,
            action: { label: 'Fix WhatsApp routing', href: `/dashboard/mps/${issue.tenant_id}#whatsapp` },
        });
    }

    if (outbound.status === 'red' || outbound.status === 'amber') {
        const failed = Number(outbound.failed_outbound_24h || 0);
        incidents.push({
            id: 'outbound',
            scope: 'platform',
            kind: 'outbound_failures',
            severity: severityFromHealthStatus(outbound.status),
            title: outbound.status === 'red' ? 'Outbound replies are failing' : 'Some outbound replies failed',
            detail: outbound.detail || null,
            affected: failed ? `${failed} failed in the last 24 hours` : null,
            action: { label: 'Open failures', href: `${MESSAGING}#failures` },
        });
    }

    if (webhook.status === 'red' || webhook.status === 'amber') {
        incidents.push({
            id: 'inbound',
            scope: 'platform',
            kind: 'inbound_processing',
            severity: severityFromHealthStatus(webhook.status),
            title: webhook.status === 'red' ? 'Inbound processing is failing' : 'Inbound processing needs review',
            detail: webhook.detail || null,
            affected: null,
            action: { label: 'Open inbound', href: '/dashboard/system/whatsapp-inbound' },
        });
    }

    return incidents;
}

/** Configured vs total active tenants, as reported by the backend. */
export function routingCoverage(whatsapp) {
    const routing = whatsapp?.routing;
    if (!routing || routing.active_tenants === undefined) return null;
    return {
        configured: Number(routing.configured_tenants || 0),
        active: Number(routing.active_tenants || 0),
        misconfigured: Number(routing.misconfigured_tenants || 0),
    };
}

/** Per-tenant outbound status counts from a page of outbound rows. */
export function outboundByTenant(items = []) {
    const byTenant = new Map();
    for (const row of items) {
        const key = row.tenant_id ?? 'unassigned';
        if (!byTenant.has(key)) {
            byTenant.set(key, {
                tenantId: row.tenant_id ?? null,
                tenantName: row.tenant_name || null,
                pending: 0,
                retrying: 0,
                failed: 0,
                sent: 0,
                lastError: null,
            });
        }
        const entry = byTenant.get(key);
        const status = String(row.status || '').toLowerCase();
        if (status in entry) entry[status] += 1;
        if (status === 'failed' && !entry.lastError && row.last_error) entry.lastError = row.last_error;
    }
    return [...byTenant.values()];
}

/** Account delivery failures: tenants with at least one failed send. */
export function accountDeliveryFailures(items = []) {
    return outboundByTenant(items)
        .filter((entry) => entry.failed > 0)
        .sort((a, b) => b.failed - a.failed);
}

/** Extracts a Meta Graph error code from free-text last_error, if present. */
export function metaErrorCode(text) {
    const value = String(text || '');
    const match = value.match(/"code"\s*:\s*(\d{2,6})/) || value.match(/\(#(\d{2,6})\)/) || value.match(/\berror(?: code)?[\s:#]+(\d{3,6})\b/i);
    return match ? match[1] : null;
}

/**
 * Groups failed rows by cause. The cause key is the Meta error code when the
 * error text carries one, otherwise the normalised first line of the error.
 */
export function groupFailuresByCause(items = []) {
    const groups = new Map();
    for (const row of items) {
        if (String(row.status || '').toLowerCase() !== 'failed') continue;
        const text = String(row.last_error || '').trim();
        const code = metaErrorCode(text);
        const summary = text.split('\n')[0].slice(0, 160) || 'Unknown error';
        const key = code ? `code:${code}` : `text:${summary.toLowerCase()}`;
        if (!groups.has(key)) {
            groups.set(key, { key, code, summary, count: 0, tenantIds: new Set(), latest: null });
        }
        const group = groups.get(key);
        group.count += 1;
        if (row.tenant_id !== undefined && row.tenant_id !== null) group.tenantIds.add(row.tenant_id);
        const at = row.last_attempt_at || row.created_at || null;
        if (at && (!group.latest || at > group.latest)) group.latest = at;
    }
    return [...groups.values()]
        .map((group) => ({ ...group, tenantIds: [...group.tenantIds] }))
        .sort((a, b) => b.count - a.count);
}
