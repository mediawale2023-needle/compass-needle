/**
 * Account-level derivations shared by Command Centre, Account 360 and
 * Messaging. Each reason cites the real signal that produced it.
 */
import { highestSeverity, severityFromAlert } from './severity';

/**
 * Launch readiness from tenants.onboarding_state (keys written by
 * PATCH /api/admin/mps/{id}/onboarding) plus WhatsApp routing.
 */
export const LAUNCH_STEPS = [
    { key: 'geography', label: 'Geography' },
    { key: 'staff', label: 'Staff' },
    { key: 'test_sent', label: 'Live smoke test' },
    { key: 'live', label: 'Production traffic' },
];

export function launchReadiness(onboardingState = {}) {
    const steps = LAUNCH_STEPS.map((step) => ({ ...step, done: Boolean(onboardingState?.[step.key]) }));
    const done = steps.filter((step) => step.done).length;
    return { steps, done, total: steps.length, complete: done === steps.length };
}

/**
 * Health for one account.
 * @param {object} input
 * @param {number|string} input.tenantId
 * @param {Array} [input.alerts]           /api/admin/alerts items
 * @param {Array} [input.whatsappIncidents] deriveWhatsAppIncidents() output
 * @param {Array} [input.deliveryFailures]  accountDeliveryFailures() output
 */
export function accountHealth({ tenantId, alerts = [], whatsappIncidents = [], deliveryFailures = [] }) {
    const id = String(tenantId);
    const reasons = [];

    for (const incident of whatsappIncidents) {
        if (incident.scope === 'platform') {
            reasons.push({ severity: incident.severity, label: incident.title, source: 'whatsapp_platform' });
        } else if (String(incident.tenantId) === id) {
            reasons.push({ severity: incident.severity, label: incident.title, detail: incident.detail, source: 'whatsapp_routing' });
        }
    }

    const failures = deliveryFailures.find((entry) => String(entry.tenantId) === id);
    if (failures?.failed) {
        reasons.push({ severity: 'warning', label: `${failures.failed} failed WhatsApp ${failures.failed === 1 ? 'reply' : 'replies'}`, detail: failures.lastError, source: 'whatsapp_delivery' });
    }

    for (const alert of alerts) {
        if (alert.tenant_id === undefined || String(alert.tenant_id) !== id) continue;
        reasons.push({ severity: severityFromAlert(alert), label: alert.title, detail: alert.description, source: alert.type });
    }

    const severity = reasons.length ? highestSeverity(reasons.map((reason) => reason.severity)) : 'ok';
    return { severity, reasons };
}
