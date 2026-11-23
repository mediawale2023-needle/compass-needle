export const PERIODS = [7, 30, 90];

export function fmtPct(value) {
    return value === null || value === undefined ? '—' : `${Math.round(value * 100)}%`;
}

export function fmtDays(value) {
    return value === null || value === undefined ? '—' : `${value}d`;
}

export function fmtCount(value) {
    return value === null || value === undefined ? '—' : Number(value).toLocaleString('en-IN');
}

export const SEAT_STATUS = {
    active: { label: 'Live', variant: 'success' },
    paused: { label: 'Paused', variant: 'secondary' },
};

/** "#B8860B" -> "43 89% 38%" so it can drive the shadcn `--primary` token. Falls back to null if invalid. */
export function hexToHslTriplet(hex) {
    if (typeof hex !== 'string' || !/^#[0-9a-fA-F]{6}$/.test(hex)) return null;
    const r = parseInt(hex.slice(1, 3), 16) / 255;
    const g = parseInt(hex.slice(3, 5), 16) / 255;
    const b = parseInt(hex.slice(5, 7), 16) / 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const l = (max + min) / 2;
    let h = 0;
    let s = 0;
    if (max !== min) {
        const d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
        else if (max === g) h = (b - r) / d + 2;
        else h = (r - g) / d + 4;
        h *= 60;
    }
    return `${Math.round(h)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}

/**
 * Portfolio health for one client, from aggregate figures only.
 *   attention: 5+ critical threads, or under half resolved (with at least 10 received)
 *   watch:     any critical thread, or under 65% resolved (with at least 10 received)
 */
export function clientHealth(client) {
    if (client?.status !== 'active' || !client.summary) return { level: 'paused', rank: -1 };
    const s = client.summary;
    const rate = s.resolution_rate;
    const enough = (s.total || 0) >= 10;
    let level = 'ok';
    if ((s.critical || 0) >= 5 || (enough && rate !== null && rate !== undefined && rate < 0.5)) level = 'attention';
    else if ((s.critical || 0) >= 1 || (enough && rate !== null && rate !== undefined && rate < 0.65)) level = 'watch';
    const rank = { attention: 2, watch: 1, ok: 0 }[level] * 10000 + (s.critical || 0) * 10 + (1 - (rate ?? 1));
    return { level, rank };
}

export function healthReasons(client) {
    const s = client?.summary;
    if (!s) return '';
    const out = [];
    if (s.critical) out.push(`${s.critical} critical`);
    if (s.resolution_rate !== null && s.resolution_rate !== undefined && s.total >= 10) out.push(`${fmtPct(s.resolution_rate)} resolved`);
    if (s.open) out.push(`${s.open} still open`);
    return out.join(' · ');
}

export const SEAT_LABEL = { mp: 'MP', mla: 'MLA' };

/** Clock time in India Standard Time, whatever the viewer's own time zone. */
export function fmtTimeIST(date) {
    return `${date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' })} IST`;
}
