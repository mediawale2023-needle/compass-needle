export const PERIODS = [7, 30, 90];

export function fmtPct(value) {
    return value === null || value === undefined ? '—' : `${Math.round(value * 100)}%`;
}

export function fmtDays(value) {
    return value === null || value === undefined ? '—' : `${value}d`;
}

export function fmtCount(value) {
    return value === null || value === undefined ? '—' : String(value);
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
