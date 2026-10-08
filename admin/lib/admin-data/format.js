/** Formatting helpers. None of these invent values: missing input → null/fallback. */

const countFormatter = new Intl.NumberFormat('en-IN');

export function formatCount(value) {
    if (value === null || value === undefined || value === '' || Number.isNaN(Number(value))) return null;
    return countFormatter.format(Number(value));
}

export function pluralize(count, singular, plural = `${singular}s`) {
    return `${count} ${Number(count) === 1 ? singular : plural}`;
}

function toDate(value) {
    if (!value) return null;
    // Backend timestamps are naive UTC ISO strings; treat them as UTC.
    const text = typeof value === 'string' && !/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? `${value}Z` : value;
    const date = new Date(text);
    return Number.isNaN(date.getTime()) ? null : date;
}

/** "just now", "11 min ago", "6 h ago", "3 days ago"; null when unknown. */
export function formatRelative(value, now = new Date()) {
    const date = toDate(value);
    if (!date) return null;
    const seconds = Math.round((now.getTime() - date.getTime()) / 1000);
    if (seconds < 0) return 'just now';
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} h ago`;
    const days = Math.floor(hours / 24);
    return days === 1 ? '1 day ago' : `${days} days ago`;
}

/** Hours elapsed since a timestamp, rounded down; null when unknown. */
export function hoursSince(value, now = new Date()) {
    const date = toDate(value);
    if (!date) return null;
    return Math.max(0, Math.floor((now.getTime() - date.getTime()) / 3_600_000));
}

/** Masks a phone number to its last three digits: "+91 ••• 730". */
export function maskPhone(value) {
    const digits = String(value || '').replace(/\D/g, '');
    if (digits.length < 4) return null;
    const country = digits.length > 10 ? `+${digits.slice(0, digits.length - 10)} ` : '';
    return `${country}••• ${digits.slice(-3)}`;
}

export function initialsFor(name) {
    const words = String(name || '').trim().split(/\s+/).filter(Boolean);
    if (!words.length) return '?';
    if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
    return `${words[0][0]}${words[words.length - 1][0]}`.toUpperCase();
}

// Deterministic, name-derived avatar tint so the same account always gets
// the same colour across screens. Purely presentational.
const AVATAR_TINTS = ['forest', 'sand', 'slate', 'plum', 'clay', 'stone'];
export function avatarTintFor(key) {
    const text = String(key ?? '');
    let hash = 0;
    for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
    return AVATAR_TINTS[hash % AVATAR_TINTS.length];
}
