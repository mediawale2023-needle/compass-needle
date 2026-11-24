export const PERIODS = [7, 30, 90];

/*
 * Reporting periods. A period is one of:
 *   { kind: 'days', days: 30 }               last N days, ending now
 *   { kind: 'all' }                          complete history
 *   { kind: 'custom', from: 'YYYY-MM-DD', to: 'YYYY-MM-DD' }   inclusive calendar dates
 */
export const DEFAULT_PERIOD = { kind: 'days', days: 30 };
export const PERIOD_PRESETS = [
    { key: 'd7', label: '7 days', period: { kind: 'days', days: 7 } },
    { key: 'd30', label: '30 days', period: { kind: 'days', days: 30 } },
    { key: 'd90', label: '90 days', period: { kind: 'days', days: 90 } },
    { key: 'd365', label: '1 year', period: { kind: 'days', days: 365 } },
    { key: 'all', label: 'All time', period: { kind: 'all' } },
];

/** Accepts a period object or a bare number of days (older callers). */
export function toPeriod(value) {
    if (typeof value === 'number') return { kind: 'days', days: value };
    return value && value.kind ? value : DEFAULT_PERIOD;
}

export function periodKey(value) {
    const p = toPeriod(value);
    if (p.kind === 'all') return 'all';
    if (p.kind === 'custom') return `${p.from}_${p.to}`;
    return `d${p.days}`;
}

/** Query string for the partner API: days=N | range=all | from=…&to=… */
export function periodQuery(value) {
    const p = toPeriod(value);
    if (p.kind === 'all') return 'range=all';
    if (p.kind === 'custom') return `from=${encodeURIComponent(p.from)}&to=${encodeURIComponent(p.to)}`;
    return `days=${encodeURIComponent(p.days)}`;
}

const DATE_FMT = { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' };
export function fmtDate(iso) {
    if (!iso) return '';
    const d = new Date(`${iso}T00:00:00Z`);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-GB', DATE_FMT);
}

/** Lower-case phrase for sentences: "the last 30 days", "all time", "1 Jan 2026 – 24 Nov 2026". */
export function periodPhrase(value) {
    const p = toPeriod(value);
    if (p.kind === 'all') return 'all time';
    if (p.kind === 'custom') return `${fmtDate(p.from)} – ${fmtDate(p.to)}`;
    if (p.days === 365) return 'the last 12 months';
    return `the last ${p.days} days`;
}

/** Title-case label for eyebrows and headings. */
export function periodLabel(value) {
    const p = toPeriod(value);
    if (p.kind === 'all') return 'All time';
    if (p.kind === 'custom') return `${fmtDate(p.from)} – ${fmtDate(p.to)}`;
    return p.days === 365 ? 'Last 12 months' : `Last ${p.days} days`;
}

/** What the server actually covered, e.g. all time starts at the first case: "All time (since 3 May 2025)". */
export function windowLabel(win, fallback) {
    if (!win) return periodLabel(fallback);
    if (win.kind === 'all') return win.from ? `All time (since ${fmtDate(win.from)})` : 'All time';
    if (win.kind === 'custom') return `${fmtDate(win.from)} – ${fmtDate(win.to)}`;
    return periodLabel({ kind: 'days', days: win.days });
}

const BUCKET_NAMES = { 1: 'day', 7: 'week', 14: 'fortnight', 30: 'month', 91: 'quarter', 182: 'half-year', 365: 'year' };
export function bucketName(days) {
    return BUCKET_NAMES[days] || `${days} days`;
}

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
