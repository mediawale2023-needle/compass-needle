'use client';

export const briefcasePalette = {
    paper: '#F2EBD9',
    paperDeep: '#E8E0CB',
    surface: '#FBF6E7',
    surfaceWarm: '#F7F0DC',
    hair: 'rgba(26,24,18,0.14)',
    hairStrong: 'rgba(26,24,18,0.32)',
    ink: '#1A1812',
    ink2: '#4A453A',
    ink3: '#7A7263',
    green: '#006A4D',
    greenDeep: '#003B2A',
    greenInk: '#024A36',
    greenTint: '#DFE9E2',
    greenWash: '#E8F0EB',
    saffron: '#C76A1A',
    saffronTint: '#F4E3CE',
    red: '#8B2E1F',
    redTint: '#F2DAD3',
    blue: '#23496B',
    blueTint: '#DDE5EE',
    neutralTint: '#E8E2CC',
};

export const briefcaseFonts = {
    serif: '"Source Serif 4", Georgia, serif',
    mono: '"JetBrains Mono", "Fira Code", monospace',
    sans: '"Inter", system-ui, sans-serif',
};

export const TABS = [
    { key: 'all_cases', label: 'All cases', countKey: 'all_cases' },
    { key: 'new', label: 'New', countKey: 'new' },
    { key: 'in_progress', label: 'In progress', countKey: 'in_progress' },
    { key: 'resolved', label: 'Resolved', countKey: 'resolved' },
    { key: 'others', label: 'Others', countKey: 'others' },
    { key: 'clusters', label: 'Clusters' },
    { key: 'deleted', label: 'Deleted' },
];

// Values + labels drive the status <select>s; colour is applied by
// getStatusBadge via the shared Overview token palette (no Tailwind colour
// utilities, no blue/purple/slate).
const STATUS_TONE = {
    new:               { bg: '#ECE6D8', fg: '#544E40' },
    awaiting_location: { bg: '#F2E6CF', fg: '#7C5514' },
    pending_review:    { bg: '#F1DED0', fg: '#8A4A22' },
    in_progress:       { bg: '#ECE6D8', fg: '#544E40' },
    resolved:          { bg: '#E0E8DA', fg: '#245F45' },
    closed:            { bg: '#ECE6D8', fg: '#6C6858' },
    irrelevant:        { bg: '#ECE6D8', fg: '#6C6858' },
};

export const STATUS_OPTIONS = [
    { value: 'new', label: 'New' },
    { value: 'awaiting_location', label: 'Needs Location' },
    { value: 'pending_review', label: 'Needs Review' },
    { value: 'in_progress', label: 'In Progress' },
    { value: 'resolved', label: 'Resolved' },
    { value: 'closed', label: 'Closed' },
    { value: 'irrelevant', label: 'Irrelevant' },
];

export const OTHER_CATEGORIES = [
    'Request',
    'Personal Request',
    'Personal request',
    'Greetings',
    'Greeting',
    'Spam',
    'Spam (Offensive)',
    'Political / Support Message',
    'Community / Event Invitation',
    'Media / Press Outreach',
    'Donation / Sponsorship Request',
    'Suggestion / Idea',
    'Spam / Promotional / Irrelevant',
];
export const OTHER_STATUSES = ['offensive', 'irrelevant', 'abusive'];

export function getStatusBadge(status) {
    const key = (status || '').toLowerCase();
    const option = STATUS_OPTIONS.find((item) => item.value === key);
    const tone = STATUS_TONE[key] || { bg: '#ECE6D8', fg: '#6C6858' };
    return (
        <span
            style={{
                display: 'inline-flex', alignItems: 'center',
                border: '1px solid #C9BFA9', padding: '2px 7px',
                fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
                fontSize: 9.5, fontWeight: 600, letterSpacing: '.03em',
                textTransform: 'uppercase', lineHeight: 1.15,
                background: tone.bg, color: tone.fg, whiteSpace: 'nowrap',
            }}
        >
            {option ? option.label : (status || '—')}
        </span>
    );
}

export function BriefcaseIcon({ name, size = 14, color = 'currentColor', stroke = 1.5 }) {
    const icons = {
        search: <><circle cx="11" cy="11" r="6" /><path d="M16 16l5 5" /></>,
        bell: <><path d="M6 16V10a6 6 0 0112 0v6l2 2H4z" /><path d="M10 20h4" /></>,
        sparkle: <><path d="M12 4v6M12 14v6M4 12h6M14 12h6M7 7l3 3M14 14l3 3" /></>,
        arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
        cluster: <><circle cx="7" cy="7" r="3" /><circle cx="17" cy="8" r="2.5" /><circle cx="9" cy="17" r="2.5" /><circle cx="18" cy="16" r="2.5" /><path d="M7 7l10 1M9 17l9-1M7 7l2 10" /></>,
        plus: <><path d="M12 5v14M5 12h14" /></>,
        eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></>,
        chevr: <><path d="M9 6l6 6-6 6" /></>,
        chev: <><path d="M6 9l6 6 6-6" /></>,
        refresh: <><path d="M4 12a8 8 0 0114-5.3L20 9M20 4v5h-5M20 12a8 8 0 01-14 5.3L4 15M4 20v-5h5" /></>,
        download: <><path d="M12 4v12M6 12l6 6 6-6M5 20h14" /></>,
        assign: <><circle cx="9" cy="9" r="4" /><path d="M3 21c0-4 3-6 6-6s6 2 6 6" /><path d="M17 11l2 2 4-4" /></>,
        check: <><path d="M5 12l5 5 9-11" /></>,
        x: <><path d="M6 6l12 12M18 6L6 18" /></>,
        translate: <><path d="M3 5h12M9 3v2M5 9c1 5 4 7 8 7M13 7c-1 4-3 7-7 9" /><path d="M14 21l4-10 4 10M15.5 17h5" /></>,
        dot: <><circle cx="12" cy="12" r="3" /></>,
        pin: <><path d="M12 21s7-7 7-12a7 7 0 10-14 0c0 5 7 12 7 12z" /><circle cx="12" cy="9" r="2.5" /></>,
        clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
        warn: <><path d="M12 3l10 17H2z" /><path d="M12 10v5M12 18v.5" /></>,
        briefcase: <><rect x="3" y="7" width="18" height="13" rx="1" /><path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2M3 13h18" /></>,
        drafter: <><path d="M4 19l4-1 12-12-3-3L5 15z" /><path d="M14 6l3 3" /></>,
    };

    return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round">
            {icons[name] || null}
        </svg>
    );
}

export function BriefcaseStatusPill({ status }) {
    const normalized = (status || '').toLowerCase();
    const map = {
        new: { fg: briefcasePalette.blue, bg: briefcasePalette.blueTint, icon: 'dot', label: 'New' },
        pending_review: { fg: briefcasePalette.saffron, bg: briefcasePalette.saffronTint, icon: 'clock', label: 'Pending' },
        in_progress: { fg: briefcasePalette.greenInk, bg: briefcasePalette.greenTint, icon: 'sparkle', label: 'In progress' },
        resolved: { fg: briefcasePalette.greenInk, bg: briefcasePalette.greenTint, icon: 'check', label: 'Resolved' },
        awaiting_location: { fg: briefcasePalette.ink, bg: briefcasePalette.neutralTint, icon: 'pin', label: 'Needs location' },
    };
    const pill = map[normalized] || map.new;
    return (
        <span
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                padding: '2px 8px 2px 6px',
                background: pill.bg,
                color: pill.fg,
                fontSize: 10.5,
                fontWeight: 600,
                letterSpacing: '0.02em',
                whiteSpace: 'nowrap',
            }}
        >
            <BriefcaseIcon name={pill.icon} size={10} color={pill.fg} stroke={2} />
            {pill.label}
        </span>
    );
}

export function formatBriefcaseAge(createdAt) {
    if (!createdAt) return '—';
    const diffMs = Date.now() - new Date(createdAt).getTime();
    const minutes = Math.max(1, Math.floor(diffMs / 60000));
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h`;
    return `${Math.floor(hours / 24)}d`;
}

export function formatLanguageTag(caseItem) {
    const raw = (
        caseItem.case_metadata?.detected_language ||
        caseItem.case_metadata?.language ||
        caseItem.detected_language ||
        ''
    ).trim();
    if (!raw) return 'UNK';
    if (/hing/i.test(raw)) return 'HING';
    if (/mar/i.test(raw)) return 'MAR';
    if (/hin/i.test(raw)) return 'HIN';
    if (/kan/i.test(raw)) return 'KAN';
    if (/tam/i.test(raw)) return 'TAM';
    if (/tel/i.test(raw)) return 'TEL';
    if (/ben/i.test(raw)) return 'BEN';
    if (/guj/i.test(raw)) return 'GUJ';
    if (/pun/i.test(raw)) return 'PUN';
    if (/mal/i.test(raw)) return 'MAL';
    if (/urd/i.test(raw)) return 'URD';
    if (/odi/i.test(raw)) return 'ODI';
    if (/assam|asm/i.test(raw)) return 'ASM';
    if (/eng/i.test(raw)) return 'ENG';
    if (/unknown/i.test(raw)) return 'UNK';
    return String(raw).slice(0, 4).toUpperCase();
}

export function getBriefcaseCitizenName(caseItem) {
    return (
        caseItem.contact_name ||
        caseItem.display_name ||
        caseItem.case_metadata?.display_name ||
        caseItem.case_metadata?.citizen_name ||
        caseItem.user_name ||
        'Citizen'
    );
}
