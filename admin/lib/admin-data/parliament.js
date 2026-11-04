/**
 * Parliament sync freshness from /api/admin/parliament/sync/status.
 * Reports facts (latest successful sync, age, backend statuses); it does not
 * classify "late" unless the caller passes an explicit threshold.
 */
import { hoursSince } from './format';

export function parliamentFreshness(tenants = [], { now = new Date(), staleAfterHours = null } = {}) {
    const enabled = tenants.filter((tenant) => tenant.parliament_sync_enabled !== false);
    const synced = enabled.map((tenant) => tenant.parliament_last_synced).filter(Boolean).sort();
    const latest = synced.length ? synced[synced.length - 1] : null;
    const statusCounts = {};
    for (const tenant of enabled) {
        const status = tenant.parliament_sync_status || 'pending';
        statusCounts[status] = (statusCounts[status] || 0) + 1;
    }
    const neverSynced = enabled.filter((tenant) => !tenant.parliament_last_synced).length;
    const stale = staleAfterHours === null
        ? null
        : enabled.filter((tenant) => {
            const age = hoursSince(tenant.parliament_last_synced, now);
            return age !== null && age >= staleAfterHours;
        }).length;
    return {
        accounts: enabled.length,
        latestSync: latest,
        hoursSinceLatest: hoursSince(latest, now),
        neverSynced,
        stale,
        statusCounts,
    };
}
