import { describe, expect, it } from 'vitest';
import {
    accountDeliveryFailures, accountHealth, countAlertsBySeverity, deriveWhatsAppIncidents, formatRelative,
    groupFailuresByCause, highestSeverity, launchReadiness, maskPhone, metaErrorCode, navSignals,
    parliamentFreshness, platformCondition, routingCoverage, severityFromAlert, initialsFor,
} from '@/lib/admin-data';

const healthy = {
    meta_token: { configured: true, status: 'green', detail: 'Authenticated as Needle.' },
    routing: { status: 'green', active_tenants: 18, configured_tenants: 18, misconfigured_tenants: 0, tenant_issues: [] },
    outbound: { status: 'green', failed_outbound_24h: 0 },
    webhook: { status: 'green' },
};

describe('severity', () => {
    it('maps backend alert severities exactly as the Command Centre labels them', () => {
        expect(severityFromAlert({ severity: 'critical' })).toBe('critical');
        expect(severityFromAlert({ severity: 'error' })).toBe('critical');
        expect(severityFromAlert({ severity: 'warning' })).toBe('warning');
        expect(severityFromAlert({ severity: 'info' })).toBe('review');
    });
    it('counts and ranks', () => {
        expect(countAlertsBySeverity([{ severity: 'error' }, { severity: 'warning' }, { severity: 'info' }])).toEqual({ critical: 1, warning: 1, review: 1, total: 3 });
        expect(highestSeverity(['review', 'warning', 'ok'])).toBe('warning');
        expect(highestSeverity([])).toBe('ok');
    });
});

describe('WhatsApp incident model', () => {
    it('produces nothing when healthy', () => {
        expect(deriveWhatsAppIncidents(healthy)).toEqual([]);
        expect(deriveWhatsAppIncidents(null)).toEqual([]);
    });

    it('treats an invalid global token as ONE platform-wide incident, never per number', () => {
        const incidents = deriveWhatsAppIncidents({ ...healthy, meta_token: { configured: true, status: 'red', detail: 'Error validating access token' } });
        expect(incidents).toHaveLength(1);
        expect(incidents[0]).toMatchObject({ scope: 'platform', kind: 'meta_token_invalid', severity: 'critical', affected: 'All WhatsApp accounts' });
        expect(incidents[0].tenantId).toBeUndefined();
        expect(JSON.stringify(incidents)).not.toMatch(/reconnect/i);
    });

    it('turns tenant routing gaps into account-specific incidents with a real fix link', () => {
        const incidents = deriveWhatsAppIncidents({
            ...healthy,
            routing: { ...healthy.routing, status: 'amber', tenant_issues: [{ tenant_id: 9, name: 'Tenant #9', constituency: 'Belgaum', issue: 'missing Meta phone number ID' }] },
        });
        expect(incidents).toEqual([expect.objectContaining({
            scope: 'account', kind: 'routing_config', tenantId: 9, detail: 'missing Meta phone number ID',
            action: { label: 'Fix WhatsApp routing', href: '/dashboard/mps/9#whatsapp' },
        })]);
    });

    it('reports outbound and inbound degradation at platform scope', () => {
        const incidents = deriveWhatsAppIncidents({ ...healthy, outbound: { status: 'amber', failed_outbound_24h: 3, detail: 'x' }, webhook: { status: 'red', detail: 'y' } });
        expect(incidents.map((i) => [i.kind, i.severity])).toEqual([['outbound_failures', 'warning'], ['inbound_processing', 'critical']]);
    });

    it('reads routing coverage from backend counts only', () => {
        expect(routingCoverage(healthy)).toEqual({ configured: 18, active: 18, misconfigured: 0 });
        expect(routingCoverage({})).toBeNull();
    });
});

describe('outbound failures', () => {
    const rows = [
        { tenant_id: 1, tenant_name: 'A', status: 'failed', last_error: '{"error":{"code":131026,"message":"Message undeliverable"}}', last_attempt_at: '2026-10-06T09:12:00' },
        { tenant_id: 1, status: 'failed', last_error: '{"code": 131026}', last_attempt_at: '2026-10-06T09:20:00' },
        { tenant_id: 2, status: 'failed', last_error: 'Timeout talking to Graph API' },
        { tenant_id: 2, status: 'pending' },
        { tenant_id: 3, status: 'sent' },
    ];
    it('groups by Meta error code when present, otherwise by message', () => {
        const groups = groupFailuresByCause(rows);
        expect(groups[0]).toMatchObject({ code: '131026', count: 2, tenantIds: [1], latest: '2026-10-06T09:20:00' });
        expect(groups[1]).toMatchObject({ code: null, count: 1, summary: 'Timeout talking to Graph API' });
    });
    it('lists only accounts with failed sends', () => {
        expect(accountDeliveryFailures(rows).map((e) => [e.tenantId, e.failed, e.pending])).toEqual([[1, 2, 0], [2, 1, 1]]);
    });
    it('extracts codes from common Graph formats', () => {
        expect(metaErrorCode('(#131047) Re-engagement message')).toBe('131047');
        expect(metaErrorCode('no code here')).toBeNull();
    });
});

describe('account health & readiness', () => {
    it('keeps platform-wide incidents off individual accounts unless asked', () => {
        const incidents = deriveWhatsAppIncidents({ ...healthy, outbound: { status: 'amber', failed_outbound_24h: 3 } });
        expect(accountHealth({ tenantId: 1, whatsappIncidents: incidents })).toEqual({ severity: 'ok', reasons: [] });
        expect(accountHealth({ tenantId: 1, whatsappIncidents: incidents, includePlatform: true }).severity).toBe('warning');
    });

    it('combines routing, delivery and alert evidence with reasons', () => {
        const incidents = deriveWhatsAppIncidents({ ...healthy, routing: { ...healthy.routing, tenant_issues: [{ tenant_id: 4, issue: 'missing tenant WhatsApp number' }] } });
        const health = accountHealth({
            tenantId: 4,
            whatsappIncidents: incidents,
            deliveryFailures: [{ tenantId: 4, failed: 2 }],
            alerts: [{ tenant_id: 4, severity: 'info', type: 'setup_incomplete', title: 'X — setup incomplete' }, { tenant_id: 5, severity: 'critical', title: 'other' }],
        });
        expect(health.severity).toBe('warning');
        expect(health.reasons.map((r) => r.source)).toEqual(['whatsapp_routing', 'whatsapp_delivery', 'setup_incomplete']);
        expect(accountHealth({ tenantId: 6 })).toEqual({ severity: 'ok', reasons: [] });
    });
    it('reads launch readiness from onboarding_state keys', () => {
        expect(launchReadiness({ geography: true, staff: true })).toMatchObject({ done: 2, total: 4, complete: false });
        expect(launchReadiness(null).done).toBe(0);
    });
});

describe('parliament freshness', () => {
    const now = new Date('2026-10-06T10:00:00Z');
    const tenants = [
        { parliament_last_synced: '2026-10-06T03:40:00', parliament_sync_status: 'synced' },
        { parliament_last_synced: '2026-10-05T03:40:00', parliament_sync_status: 'synced' },
        { parliament_last_synced: null, parliament_sync_status: 'needs_review' },
        { parliament_sync_enabled: false, parliament_last_synced: '2026-01-01T00:00:00' },
    ];
    it('reports facts and only classifies stale with an explicit threshold', () => {
        const f = parliamentFreshness(tenants, { now });
        expect(f).toMatchObject({ accounts: 3, latestSync: '2026-10-06T03:40:00', hoursSinceLatest: 6, neverSynced: 1, stale: null });
        expect(f.statusCounts).toEqual({ synced: 2, needs_review: 1 });
        expect(parliamentFreshness(tenants, { now, staleAfterHours: 24 }).stale).toBe(1);
    });
});

describe('navigation signals', () => {
    const alerts = [
        { type: 'whatsapp_health', severity: 'critical', title: 'WhatsApp is degraded' },
        { type: 'setup_incomplete', severity: 'info', tenant_id: 3, title: 'B — setup incomplete' },
        { type: 'job_failed', severity: 'warning', title: 'parliament_backfill_all failed' },
    ];
    it('derives sidebar counts from real alerts only', () => {
        expect(navSignals(alerts)).toEqual({
            messaging: { count: 1, severity: 'critical' },
            command: { count: 2, severity: 'critical' },
            onboarding: { count: 1, severity: 'review' },
            system: { count: 1, severity: 'warning' },
        });
        expect(navSignals(null)).toEqual({});
    });
    it('never claims health without evidence', () => {
        expect(platformCondition(null)).toBeNull();
        expect(platformCondition([])).toMatchObject({ severity: 'ok' });
        expect(platformCondition(alerts)).toMatchObject({ severity: 'critical', title: '2 platform alerts', detail: 'WhatsApp is degraded' });
    });
});

describe('formatting', () => {
    const now = new Date('2026-10-06T10:00:00Z');
    it('formats relative time from naive UTC timestamps', () => {
        expect(formatRelative('2026-10-06T09:49:00', now)).toBe('11 min ago');
        expect(formatRelative('2026-10-06T04:00:00', now)).toBe('6 h ago');
        expect(formatRelative(null, now)).toBeNull();
    });
    it('masks phones to the last three digits and builds initials', () => {
        expect(maskPhone('+91 98290 41730')).toBe('+91 ••• 730');
        expect(maskPhone('12')).toBeNull();
        expect(initialsFor('Avichal Dubey')).toBe('AD');
    });
});

import { buildAttentionItems, caseTrend, countAttention, formatDuration, openOverDays } from '@/lib/admin-data';

describe('needs-attention queue', () => {
    const health = {
        meta_token: { configured: true, status: 'red', detail: 'Error validating access token' },
        routing: { status: 'amber', active_tenants: 3, configured_tenants: 2, tenant_issues: [{ tenant_id: 5, name: 'X', issue: 'missing Meta phone number ID' }] },
        outbound: { status: 'green' },
        webhook: { status: 'green' },
    };
    const alerts = [
        { type: 'setup_incomplete', severity: 'info', tenant_id: 3, title: 'B — setup incomplete' },
        { type: 'whatsapp_health', severity: 'critical', title: 'WhatsApp is degraded' },
        { type: 'job_failed', severity: 'warning', title: 'job failed' },
        { type: 'tenant_inactive', severity: 'warning', tenant_id: 9, title: 'Z has gone stale' },
    ];

    it('returns null when alerts are unavailable', () => {
        expect(buildAttentionItems({ alerts: null })).toBeNull();
    });

    it('replaces the generic WhatsApp alert with precise incidents and ranks deterministically', () => {
        const items = buildAttentionItems({ alerts, whatsapp: health, accounts: { 5: { name: 'Priya', detail: 'Thrissur' } } });
        expect(items.map((item) => item.kind)).toEqual(['meta_token_invalid', 'job_failed', 'routing_config', 'tenant_inactive', 'setup_incomplete']);
        expect(items[0]).toMatchObject({ scope: 'platform', tenantId: null, account: null, action: { label: 'Open Messaging' } });
        expect(items.find((item) => item.kind === 'routing_config').account).toEqual({ name: 'Priya', detail: 'Thrissur' });
        expect(items.find((item) => item.kind === 'tenant_inactive').account.name).toBe('Account #9');
        expect(items.some((item) => item.kind === 'whatsapp_health')).toBe(false);
        expect(countAttention(items)).toMatchObject({ critical: 1, warning: 3, review: 1, total: 5 });
    });

    it('keeps the backend WhatsApp alert when health is unavailable', () => {
        const items = buildAttentionItems({ alerts, whatsapp: null });
        expect(items[0]).toMatchObject({ kind: 'whatsapp_health', severity: 'critical', action: { label: 'Open Messaging', href: '/dashboard/system/whatsapp' } });
    });

    it('routes every action to a real Admin destination', () => {
        const items = buildAttentionItems({ alerts, whatsapp: health });
        for (const item of items) expect(item.action.href).toMatch(/^\/dashboard\//);
    });
});

describe('case analytics derivations', () => {
    const aggregates = {
        open_now: 9,
        weekly: [
            { week_start: '2026-09-21', new: 5, resolved: 3, open_at_end: 6 },
            { week_start: '2026-09-28', new: 4, resolved: 2, open_at_end: 8 },
            { week_start: '2026-10-05', new: 1, resolved: 0, open_at_end: 9 },
        ],
        ageing: [{ min_days: 0, count: 4 }, { min_days: 8, count: 2 }, { min_days: 15, count: 2 }, { min_days: 31, count: 1 }],
    };
    it('charts completed weeks only and reports the current week separately', () => {
        const trend = caseTrend(aggregates);
        expect(trend.labels).toEqual(['21 Sep', '28 Sep']);
        expect(trend.newCases).toEqual([5, 4]);
        expect(trend.thisWeek).toMatchObject({ new: 1, resolved: 0 });
        expect(trend.openAtEnd).toEqual([6, 8, 9]);
        expect(trend.openChange).toBe(1);
        expect(caseTrend({ weekly: [] })).toBeNull();
    });
    it('sums ageing bands above a threshold and formats durations', () => {
        expect(openOverDays(aggregates, 14)).toBe(3);
        expect(openOverDays(null)).toBeNull();
        expect(formatDuration(60)).toBe('2.5 days');
        expect(formatDuration(5)).toBe('5 hours');
        expect(formatDuration(null)).toBeNull();
    });
});
