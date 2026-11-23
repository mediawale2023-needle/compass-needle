/**
 * Partner theme engine: one brand colour in, a contrast-safe set of CSS variables out.
 *
 * The brand colour is used only for actions, the active nav item, focus rings and links.
 * Status and chart colours are fixed in partner.css and never derived from the brand.
 */
export const DEFAULT_BRAND_COLOR = '#1F3A5F';
const INK = '#17181C';
const WHITE = '#FFFFFF';

export function isHexColor(value) {
    return typeof value === 'string' && /^#[0-9a-fA-F]{6}$/.test(value);
}

function rgb(hex) {
    return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
}

function toHex(channels) {
    return `#${channels.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('')}`.toUpperCase();
}

export function mix(a, b, t) {
    const A = rgb(a);
    const B = rgb(b);
    return toHex(A.map((v, i) => v + (B[i] - v) * t));
}

export function luminance(hex) {
    const [r, g, b] = rgb(hex).map((v) => {
        const c = v / 255;
        return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a, b) {
    const A = luminance(a);
    const B = luminance(b);
    return (Math.max(A, B) + 0.05) / (Math.min(A, B) + 0.05);
}

/** Returns { vars, report }: CSS custom properties for the partner shell and the contrast figures behind them. */
export function buildPartnerTheme(brandColor) {
    const brand = isHexColor(brandColor) ? brandColor.toUpperCase() : DEFAULT_BRAND_COLOR;
    // Text on brand-filled buttons: white when it reaches AA, otherwise near-black.
    const fg = contrast(brand, WHITE) >= 4.5 ? WHITE : INK;
    // The brand used as text (links, active labels): darken towards ink until it reaches AA on white.
    let brandInk = brand;
    for (let t = 0.05; contrast(brandInk, WHITE) < 4.5 && t <= 1; t += 0.05) brandInk = mix(brand, INK, t);
    return {
        vars: {
            '--brand': brand,
            '--brand-fg': fg,
            '--brand-ink': brandInk,
            '--brand-tint': mix(brand, WHITE, 0.91),
            '--brand-soft': mix(brand, WHITE, 0.8),
        },
        report: {
            brand,
            fg,
            brandInk,
            fgOnBrand: contrast(brand, fg),
            brandOnWhite: contrast(brand, WHITE),
            brandInkOnWhite: contrast(brandInk, WHITE),
        },
    };
}

/** Up to two initials for a monogram when the partner has no logo. */
export function initials(name) {
    const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return '·';
    return (parts.length === 1 ? parts[0].slice(0, 2) : parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
