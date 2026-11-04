/**
 * Account 360 derivations. Every value traces to a real field:
 *   /api/admin/mps/{id}/detail, /mps/{id}/geography, /cases/aggregates?tenant_id,
 *   /system-health (routing tenant_issues + platform token), /whatsapp/outbound?tenant_id,
 *   /alerts, /parliament/sync/status.
 * Platform-wide problems are reported separately and never become this
 * account's condition.
 */
import { accountDeliveryFailures, deriveWhatsAppIncidents } from './whatsapp';
import { accountHealth } from './accounts';
import { formatRelative, hoursSince } from './format';
import { buildLaunchChecklist, launchSummary } from './onboarding';

function titleCase(value) {
    const text = String(value || '');
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : '';
}

export function accountIdentity(detail, tenantId) {
    const p = detail?.profile || {};
    const seatType = detail?.seat_type || p.seat_type || '';
    const house = p.house || null;
    const role = seatType === 'mla' ? 'MLA' : seatType === 'mp' ? 'MP' : (detail?.seat_label || p.seat_label || null);
    const stage = detail?.account_stage || p.account_stage || null;
    return {
        tenantId: detail?.tenant_id ?? tenantId,
        name: p.mp_name || null,
        constituency: p.constituency && p.constituency !== 'India' ? p.constituency : null,
        state: p.state || null,
        house,
        role,
        roleLabel: [role, house && !(role === 'MLA' && house === 'Vidhan Sabha') ? house : null].filter(Boolean).join(' · ') || null,
        stage,
        stageLabel: stage ? titleCase(stage) : null,
        party: p.party || null,
        createdAt: p.created_at || null,
        lastLogin: detail?.last_login && detail.last_login !== 'Never' ? detail.last_login : null,
        seatKey: seatType && p.constituency && p.constituency !== 'India' ? `${seatType}:${p.constituency}` : null,
        whatsappNumber: p.whatsapp_number || null,
        phoneNumberId: p.phone_number_id || null,
        languages: Array.isArray(p.languages) ? p.languages : [],
        keyFacts: Array.isArray(p.key_facts) ? p.key_facts : [],
    };
}

/**
 * Condition of THIS account. Inputs may be null when a source is unavailable.
 * Returns { severity, reasons, platformIncidents, sources }.
 */
export function accountCondition({ tenantId, whatsapp = null, outboundItems = null, alerts = null }) {
    const incidents = deriveWhatsAppIncidents(whatsapp);
    const accountIncidents = incidents.filter((incident) => incident.scope === 'account');
    const platformIncidents = incidents.filter((incident) => incident.scope === 'platform');
    const failures = outboundItems ? accountDeliveryFailures(outboundItems.filter((row) => String(row.tenant_id) === String(tenantId))) : [];
    const health = accountHealth({ tenantId, alerts: alerts || [], whatsappIncidents: accountIncidents, deliveryFailures: failures });
    return {
        ...health,
        platformIncidents,
        failures: failures[0] || null,
        sources: { whatsapp: Boolean(whatsapp), outbound: Boolean(outboundItems), alerts: Boolean(alerts) },
    };
}

function tenantParliament(parliament, tenantId) {
    return (parliament?.tenants || []).find((tenant) => String(tenant.tenant_id) === String(tenantId)) || null;
}

/**
 * Six readiness columns. tone: ok | warning | review | critical | neutral.
 * status/detail strings only restate the underlying field.
 */
export function readinessColumns({ tenantId, detail, geography, whatsapp, outboundItems, parliament, cases, now = new Date() }) {
    const identity = accountIdentity(detail, tenantId);
    const routingIssue = (whatsapp?.routing?.tenant_issues || []).find((issue) => String(issue.tenant_id) === String(tenantId));
    const tenantOutbound = outboundItems ? outboundItems.filter((row) => String(row.tenant_id) === String(tenantId)) : null;
    const failed = tenantOutbound ? tenantOutbound.filter((row) => String(row.status).toLowerCase() === 'failed').length : null;
    const checklist = buildLaunchChecklist(tenantId, detail, detail?.onboarding_state || {}, geography || { assemblies: {} });
    const summary = launchSummary(checklist, detail?.onboarding_state || {});
    const staff = detail?.staff || [];
    const activeStaff = staff.filter((member) => member.is_active).length;
    const geo = checklist.find((item) => item.key === 'geography');
    const pTenant = tenantParliament(parliament, tenantId);

    const configured = Boolean(identity.whatsappNumber && identity.phoneNumberId);
    const whatsappColumn = !detail ? { tone: 'neutral', status: 'Unavailable', detail: null }
        : routingIssue ? { tone: 'warning', status: 'Routing incomplete', detail: routingIssue.issue }
        : !configured ? { tone: 'warning', status: 'Not configured', detail: identity.whatsappNumber ? 'Meta phone number ID missing' : 'No WhatsApp number' }
        : failed ? { tone: 'warning', status: `${failed} failed ${failed === 1 ? 'send' : 'sends'}`, detail: 'In the latest outbound messages' }
        : { tone: 'ok', status: 'Configured', detail: 'Number and Meta ID mapped' };

    const onboardingColumn = summary.isLive
        ? { tone: 'ok', status: 'Live', detail: 'Production traffic enabled' }
        : summary.canGoLive
            ? { tone: 'review', status: 'Ready to enable', detail: 'All checks verified' }
            : { tone: 'review', status: `${summary.completed} of ${summary.required} checks`, detail: summary.blockers[0] ? `Next: ${summary.blockers[0].label}` : null };

    const staffColumn = !detail ? { tone: 'neutral', status: 'Unavailable', detail: null }
        : activeStaff ? { tone: 'ok', status: `${activeStaff} active`, detail: staff.length > activeStaff ? `${staff.length - activeStaff} suspended` : 'Staff accounts' }
        : { tone: 'warning', status: 'No active staff', detail: staff.length ? `${staff.length} suspended` : 'Add the first staff account' };

    const geographyColumn = !geography ? { tone: 'neutral', status: 'Unavailable', detail: null }
        : geo?.done ? { tone: 'ok', status: 'Configured', detail: `${geo.meta.assemblies} assemblies · ${geo.meta.localities} localities` }
        : { tone: 'warning', status: 'Not configured', detail: 'No assembly localities saved' };

    let intelligenceColumn;
    if (!parliament) intelligenceColumn = { tone: 'neutral', status: 'Unavailable', detail: null };
    else if (!pTenant) intelligenceColumn = { tone: 'neutral', status: 'Not tracked', detail: 'No Parliament sync record' };
    else if (pTenant.parliament_sync_enabled === false) intelligenceColumn = { tone: 'neutral', status: 'Sync disabled', detail: 'Parliament sync is off' };
    else if (pTenant.parliament_sync_status === 'needs_review') intelligenceColumn = { tone: 'review', status: 'Needs review', detail: 'Member match awaits confirmation' };
    else if (pTenant.parliament_last_synced) intelligenceColumn = { tone: 'ok', status: 'Synced', detail: `Parliament data ${formatRelative(pTenant.parliament_last_synced, now)}` };
    else intelligenceColumn = { tone: 'neutral', status: 'Not synced yet', detail: titleCase(pTenant.parliament_sync_status || 'pending') };

    const over14 = cases?.ageing ? cases.ageing.filter((band) => Number(band.min_days) > 14).reduce((sum, band) => sum + Number(band.count || 0), 0) : null;
    const casesColumn = !cases ? { tone: 'neutral', status: 'Unavailable', detail: null }
        : { tone: 'neutral', status: `${cases.open_now} open`, detail: over14 ? `${over14} older than 14 days` : 'None older than 14 days' };

    return [
        { key: 'whatsapp', label: 'WhatsApp', ...whatsappColumn },
        { key: 'onboarding', label: 'Onboarding', ...onboardingColumn },
        { key: 'staff', label: 'Staff', ...staffColumn },
        { key: 'geography', label: 'Geography', ...geographyColumn },
        { key: 'intelligence', label: 'Intelligence', ...intelligenceColumn },
        { key: 'cases', label: 'Cases', ...casesColumn },
    ];
}

/** Parliament record for this account with an age in hours (null when absent). */
export function parliamentForAccount(parliament, tenantId, now = new Date()) {
    const record = tenantParliament(parliament, tenantId);
    if (!record) return null;
    return { ...record, hoursSince: hoursSince(record.parliament_last_synced, now) };
}

/** Summary of geography decisions (from /seats/geography-decisions). */
export function decisionSummary(items) {
    if (!Array.isArray(items)) return null;
    const review = items.filter((item) => item.needs_review);
    const unresolved = items.filter((item) => !item.resolved && !item.needs_review);
    const resolved = items.filter((item) => item.resolved && !item.needs_review);
    return { total: items.length, review: review.length, unresolved: unresolved.length, resolved: resolved.length, reviewItems: review };
}
