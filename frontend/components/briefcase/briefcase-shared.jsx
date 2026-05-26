'use client';

import { Badge } from '@/components/ui/badge';

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
    { key: 'needs', label: 'Needs you', countKey: 'needs', accent: briefcasePalette.saffron },
    { key: 'new', label: 'New', countKey: 'new' },
    { key: 'in_progress', label: 'In progress', countKey: 'in_progress' },
    { key: 'resolved', label: 'Resolved', countKey: 'resolved' },
    { key: 'all_cases', label: 'All cases', countKey: 'all_cases' },
    { key: 'clusters', label: 'Clusters' },
    { key: 'deleted', label: 'Deleted' },
];

export const STATUS_OPTIONS = [
    { value: 'new', label: 'New', className: 'bg-blue-100 text-blue-700' },
    { value: 'awaiting_location', label: 'Needs Location', className: 'bg-orange-100 text-orange-700' },
    { value: 'pending_review', label: 'Needs Review', className: 'bg-purple-100 text-purple-700' },
    { value: 'in_progress', label: 'In Progress', className: 'bg-amber-100 text-amber-700' },
    { value: 'resolved', label: 'Resolved', className: 'bg-green-100 text-green-700' },
    { value: 'escalated', label: 'Escalated', className: 'bg-red-100 text-red-700' },
    { value: 'closed', label: 'Closed', className: 'bg-slate-100 text-slate-600' },
    { value: 'irrelevant', label: 'Irrelevant', className: 'bg-slate-100 text-slate-500' },
];

export const OTHER_CATEGORIES = ['Request', 'Greetings', 'Spam', 'Spam (Offensive)'];
export const OTHER_STATUSES = ['offensive', 'irrelevant'];

export function getStatusBadge(status) {
    const option = STATUS_OPTIONS.find((item) => item.value === (status || '').toLowerCase());
    if (option) {
        return (
            <Badge variant="secondary" className={option.className}>
                {option.label}
            </Badge>
        );
    }
    return <Badge variant="secondary">{status}</Badge>;
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
        escalated: { fg: '#fff', bg: briefcasePalette.red, icon: 'warn', label: 'Escalated' },
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
    const raw = caseItem.case_metadata?.detected_language || caseItem.case_metadata?.language || caseItem.detected_language || 'EN';
    if (/mar/i.test(raw)) return 'MAR';
    if (/hin/i.test(raw)) return 'HIN';
    if (/kan/i.test(raw)) return 'KAN';
    if (/eng/i.test(raw)) return 'EN';
    return String(raw).slice(0, 3).toUpperCase();
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
