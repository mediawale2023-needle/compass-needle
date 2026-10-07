/**
 * Case Explorer derivations over /api/admin/cases/explorer and
 * /api/admin/cases/{id}. Pure and deterministic. Everything here describes
 * what the backend recorded; AI-derived values are kept separate and are
 * never presented as staff decisions. Nothing here implies a mutation.
 */

// Same families as compute_case_aggregates (admin_api.py) so the explorer,
// the Command Centre and Account 360 agree on what "open" means.
export const OPEN_CASE_STATUSES = ['new', 'pending', 'pending_review', 'awaiting_location', 'in_progress'];
export const RESOLVED_CASE_STATUSES = ['resolved', 'completed'];
// Same threshold the Command Centre reports as "open over 14 days".
export const AGEING_THRESHOLD_DAYS = 14;

const STATUS_META = {
    new: { label: 'New', tone: 'notice' },
    pending: { label: 'Pending', tone: 'notice' },
    pending_review: { label: 'Pending review', tone: 'review' },
    awaiting_location: { label: 'Awaiting location', tone: 'warning' },
    in_progress: { label: 'In progress', tone: 'notice' },
    resolved: { label: 'Resolved', tone: 'ok' },
    completed: { label: 'Completed', tone: 'ok' },
    closed: { label: 'Closed', tone: 'neutral' },
};

const PRIORITY_META = {
    critical: { label: 'Critical', tone: 'critical', bars: 3 },
    high: { label: 'High', tone: 'warning', bars: 2 },
    standard: { label: 'Standard', tone: 'neutral', bars: 1 },
    low: { label: 'Low', tone: 'neutral', bars: 0 },
};

export function humanize(value) {
    const text = String(value ?? '').trim();
    if (!text) return '';
    const spaced = text.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ');
    return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function caseStatusMeta(status) {
    const key = String(status || '').toLowerCase();
    return STATUS_META[key] || { label: humanize(key) || 'Unknown', tone: 'neutral' };
}

export function isOpenCase(status) {
    return OPEN_CASE_STATUSES.includes(String(status || '').toLowerCase());
}

export function casePriorityMeta(priority, critical = false) {
    const key = String(priority || '').toLowerCase();
    if (PRIORITY_META[key]) return { key, ...PRIORITY_META[key] };
    // Older rows only carry is_critical.
    return critical ? { key: 'critical', ...PRIORITY_META.critical } : { key: 'standard', ...PRIORITY_META.standard };
}

/**
 * Presets map one-to-one onto real backend filters — no invented counts and
 * no "open" preset, because the explorer's status filter takes a single
 * status and "open" spans five.
 */
export const CASE_PRESETS = [
    { value: 'all', label: 'All cases', filters: { priority: '', assignment: '' } },
    { value: 'critical', label: 'Critical', filters: { priority: 'critical', assignment: '' } },
    { value: 'unassigned', label: 'Unassigned', filters: { priority: '', assignment: 'unassigned' } },
];

export function activePreset(filters = {}) {
    const match = CASE_PRESETS.find((preset) => Object.entries(preset.filters).every(([key, value]) => (filters[key] || '') === value));
    return match ? match.value : null;
}

export const EXPLORER_FILTER_KEYS = ['mp_id', 'period', 'category', 'status', 'priority', 'assignment'];

export const PERIOD_OPTIONS = [
    { value: '7days', label: 'Last 7 days' },
    { value: '30days', label: 'Last 30 days' },
    { value: '90days', label: 'Last 90 days' },
];

export function explorerQuery(filters = {}) {
    const params = new URLSearchParams();
    EXPLORER_FILTER_KEYS.forEach((key) => {
        if (filters[key]) params.set(key, String(filters[key]));
    });
    const qs = params.toString();
    return qs ? `?${qs}` : '';
}

/** Explorer filters from URL search params; `tenant_id` (Account 360 links) maps to `mp_id`. */
export function filtersFromParams(params) {
    const get = (key) => (params && typeof params.get === 'function' ? params.get(key) : null) || '';
    const filters = {};
    EXPLORER_FILTER_KEYS.forEach((key) => { filters[key] = get(key); });
    if (!filters.mp_id) filters.mp_id = get('tenant_id');
    return filters;
}

function toDate(value) {
    if (!value || value === '-') return null;
    const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
    return Number.isNaN(date.getTime()) ? null : date;
}

/** Age since creation. Ageing tone only for OPEN cases past the shared 14-day threshold. */
export function caseAge(createdAt, status, now = new Date()) {
    const created = toDate(createdAt);
    if (!created) return { days: null, label: '—', tone: 'neutral' };
    const hours = Math.max(0, (now.getTime() - created.getTime()) / 36e5);
    const days = Math.floor(hours / 24);
    const label = hours < 1 ? '<1h' : hours < 24 ? `${Math.floor(hours)}h` : `${days}d`;
    const tone = isOpenCase(status) && days > AGEING_THRESHOLD_DAYS ? 'warning' : 'neutral';
    return { days, label, tone };
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "4 Oct 2026, 16:20" in UTC; null when absent. Timestamps are stored naive UTC. */
export function formatCaseTime(value) {
    const date = toDate(value);
    if (!date) return null;
    const pad = (n) => String(n).padStart(2, '0');
    return `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}, ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())} UTC`;
}

/** Client-side search over the rows already loaded (the API has no text search). */
export function searchCases(rows = [], query = '') {
    const needle = String(query || '').trim().toLowerCase().replace(/^#/, '');
    if (!needle) return rows;
    return rows.filter((row) => [row.id, row.case_ref, row.message, row.mp, row.location, row.assembly, row.category, row.phone]
        .some((value) => value !== null && value !== undefined && String(value).toLowerCase().includes(needle)));
}

function placeValue(value) {
    const text = String(value ?? '').trim();
    return text && text !== '-' ? text : null;
}

export function caseLocation(row = {}) {
    const location = placeValue(row.location);
    const assembly = placeValue(row.assembly);
    if (location && assembly && location.toLowerCase() !== assembly.toLowerCase()) return `${location} · ${assembly}`;
    return location || assembly || null;
}

/* ── Investigation ─────────────────────────────────────────────────── */

const FILED_GOVT_STATUSES = ['submitted', 'under_review', 'escalated', 'resolved', 'rejected'];

/** True once a government filing or routing is on record (mirrors _govt_already_filed). */
export function hasGovernmentRecord(government) {
    if (!government) return false;
    const status = String(government.status || '').toLowerCase();
    return Boolean(government.reference_number || government.department || government.portal || FILED_GOVT_STATUSES.includes(status));
}

export function governmentStatusMeta(status) {
    const key = String(status || '').toLowerCase();
    if (!key || key === 'not_forwarded') return { label: 'Not forwarded', tone: 'neutral' };
    if (key === 'resolved') return { label: 'Resolved by department', tone: 'ok' };
    if (key === 'rejected') return { label: 'Rejected by department', tone: 'critical' };
    if (key === 'escalated') return { label: 'Escalated', tone: 'warning' };
    return { label: humanize(key), tone: 'notice' };
}

function messageList(messages) {
    const inbound = Array.isArray(messages?.inbound) ? messages.inbound.map((m) => ({ ...m, direction: 'inbound' })) : [];
    const outbound = Array.isArray(messages?.outbound) ? messages.outbound.map((m) => ({ ...m, direction: 'outbound' })) : [];
    return [...inbound, ...outbound].sort((a, b) => String(a.created_at || '').localeCompare(String(b.created_at || '')));
}

export function caseMessages(detail) {
    return messageList(detail?.messages);
}

export function caseNotes(detail) {
    const notes = [];
    if (String(detail?.notes_for_staff || '').trim()) notes.push({ key: 'staff', label: 'Staff notes', body: detail.notes_for_staff.trim() });
    if (String(detail?.response_to_citizen || '').trim()) notes.push({ key: 'citizen', label: 'Response to citizen', body: detail.response_to_citizen.trim() });
    return notes;
}

/** Investigation tabs — each appears only when the backend returned real data for it. */
export function caseTabs(detail) {
    if (!detail) return [];
    const tabs = [{ value: 'overview', label: 'Overview' }];
    const activity = Array.isArray(detail.activity) ? detail.activity : [];
    if (activity.length) tabs.push({ value: 'timeline', label: 'Timeline', count: activity.length });
    if (hasGovernmentRecord(detail.government)) tabs.push({ value: 'government', label: 'Government' });
    const notes = caseNotes(detail);
    if (notes.length) tabs.push({ value: 'notes', label: 'Notes', count: notes.length });
    const messages = caseMessages(detail);
    if (messages.length) tabs.push({ value: 'messages', label: 'Messages', count: messages.length });
    return tabs;
}

function fieldList(details) {
    // case_updated rows store a Python dict repr of the changed columns.
    const keys = [...String(details || '').matchAll(/'([a-z_]+)'\s*:/g)].map((match) => match[1]);
    return [...new Set(keys)].map((key) => humanize(key).toLowerCase());
}

/** One case_activity_log row → a sentence. Unknown actions are shown as recorded. */
export function describeActivity(entry = {}) {
    const action = String(entry.action || '').toLowerCase();
    const from = entry.old_value ? caseStatusMeta(entry.old_value).label : null;
    const to = entry.new_value;
    switch (action) {
    case 'status_change':
        return from ? `Status changed from ${from} to ${caseStatusMeta(to).label}` : `Status set to ${caseStatusMeta(to).label}`;
    case 'category_confirmed':
        return `Category confirmed as ${to || '—'}`;
    case 'case_updated': {
        const fields = fieldList(entry.details);
        return fields.length ? `Case updated: ${fields.join(', ')}` : 'Case updated';
    }
    case 'ai_translated':
        return 'Citizen message machine-translated to English';
    case 'citizen_notified':
        return `Citizen notified${to ? ` (${humanize(to).toLowerCase()})` : ''}`;
    case 'deleted':
        return 'Case deleted';
    case 'restored':
        return 'Case restored';
    case 'govt_submitted':
        return `Filed with government portal${to ? ` · ref ${to}` : ''}`;
    case 'govt_resolution_reviewed':
        return `Government resolution reviewed${to ? `: ${humanize(to).toLowerCase()}` : ''}`;
    case 'complaint_added_manually':
        return 'Added manually from an existing WhatsApp thread';
    case 'ack_policy_flag':
        return 'Acknowledgement flagged by message policy';
    default:
        return humanize(action) || 'Activity recorded';
    }
}

export function activityTone(entry = {}) {
    const action = String(entry.action || '').toLowerCase();
    if (action === 'status_change' && RESOLVED_CASE_STATUSES.includes(String(entry.new_value || '').toLowerCase())) return 'ok';
    if (action === 'deleted' || action === 'ack_policy_flag') return 'warning';
    return undefined;
}

export function timelineItems(activity = [], { newestFirst = true, limit } = {}) {
    const rows = Array.isArray(activity) ? [...activity] : [];
    if (newestFirst) rows.reverse();
    const sliced = limit ? rows.slice(0, limit) : rows;
    return sliced.map((entry) => ({
        title: describeActivity(entry),
        actor: entry.username && entry.username !== 'system' ? entry.username : entry.username === 'system' ? 'System' : null,
        meta: formatCaseTime(entry.created_at),
        tone: activityTone(entry),
    }));
}

const DECIDED_BY = {
    ai: 'AI classifier',
    keyword: 'Keyword rules',
    staff: 'Staff',
    rules: 'Rules',
};

function percent(value) {
    const number = Number(value);
    if (value === null || value === undefined || Number.isNaN(number)) return null;
    return `${Math.round(number <= 1 ? number * 100 : number)}%`;
}

/**
 * AI-derived facts for the "Needle analysis" panel. Only keys the pipeline
 * actually wrote; empty when nothing was recorded.
 */
export function analysisFacts(analysis) {
    if (!analysis) return [];
    const facts = [];
    const category = [analysis.ai_category, analysis.ai_subcategory].filter(Boolean).join(' › ');
    if (category) {
        const confidence = percent(analysis.ai_confidence);
        facts.push({ label: 'Suggested category', value: confidence ? `${category} · ${confidence} confidence` : category });
    }
    if (analysis.category_decided_by) facts.push({ label: 'Category source', value: DECIDED_BY[analysis.category_decided_by] || humanize(analysis.category_decided_by) });
    if (analysis.classification_mode) {
        facts.push({ label: 'Classification mode', value: analysis.classification_mode === 'shadow' ? 'Shadow — suggestion only, not applied' : humanize(analysis.classification_mode) });
    }
    if (analysis.language) facts.push({ label: 'Detected language', value: humanize(analysis.language) });
    if (analysis.department_mentioned) facts.push({ label: 'Department mentioned', value: analysis.department_mentioned });
    if (analysis.scheme_mentioned) facts.push({ label: 'Scheme mentioned', value: analysis.scheme_mentioned });
    const geo = analysis.geography || {};
    if (geo.confidence || geo.source) {
        facts.push({ label: 'Location match', value: [geo.confidence && `${humanize(geo.confidence)} confidence`, geo.source && `via ${humanize(geo.source).toLowerCase()}`].filter(Boolean).join(' · ') });
    }
    return facts;
}

export function analysisFlags(analysis) {
    if (!analysis) return [];
    const flags = [];
    if (analysis.needs_review) flags.push('Classifier asked for staff review');
    if (analysis.geography?.needs_review) flags.push(analysis.geography.review_reason ? `Location needs review: ${humanize(analysis.geography.review_reason).toLowerCase()}` : 'Location needs review');
    return flags;
}

export function hasAnalysis(analysis) {
    return Boolean(analysis && (analysis.summary || analysisFacts(analysis).length || analysisFlags(analysis).length));
}

/** Recorded (staff/system) category — distinct from the AI suggestion. */
export function recordedCategory(detail) {
    if (!detail) return null;
    const taxonomy = [detail.problem_domain, detail.problem_subdomain].filter(Boolean).join(' › ');
    if (taxonomy) return taxonomy;
    const category = placeValue(detail.category);
    return category;
}

/** Index of the selected case in the visible list, for previous/next. */
export function neighbourIds(rows = [], selectedId) {
    const index = rows.findIndex((row) => String(row.id) === String(selectedId));
    if (index === -1) return { previous: null, next: null, index: -1 };
    return { previous: rows[index - 1]?.id ?? null, next: rows[index + 1]?.id ?? null, index };
}
