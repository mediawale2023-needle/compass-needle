'use client';

import { useEffect, useMemo, useState } from 'react';
import { BriefcaseIcon, formatBriefcaseAge } from '@/components/briefcase/briefcase-shared';

// ─── Case Detail visual language (frozen dc-1440 palette) ─────────────
const C = {
    surface:    '#FFFEFB',
    bg:         '#F3EEE2',
    hair:       '#E4DECB',
    hairSoft:   '#DDD6C5',
    ink:        '#211F19',
    muted:      '#6C6858',
    faint:      '#9D9683',
    green:      '#2B6E4C',
    greenDeep:  '#245F45',
    amber:      '#C9821C',
    amberInk:   '#B87418',
    rust:       '#A85C2F',
    err:        '#A33A32',
    errAccent:  '#B34336',
    rowHover:   '#FCFAF3',
    activeTint: '#F7F2E7',
    needleProgBg:  '#EEF2F8',
    needleProgFg:  '#335A8D',
    needleReviewBg:'#FBEEE3',
    needleReviewFg:'#B35D24',
    needleDoneBg:  '#E3ECE3',
    needleDoneFg:  '#245F45',
    needleNeutBg:  '#ECE8DC',
    needleNeutFg:  '#6C6858',
    tintGreen:  'rgba(43,110,76,.08)',
    tintAmber:  'rgba(188,106,54,.10)',
    tintDanger: 'rgba(170,55,45,.08)',
    catBg:      '#F8F4EA',
};

const SANS = '"Public Sans", "Noto Sans Devanagari", system-ui, sans-serif';
const MONO = '"IBM Plex Mono", ui-monospace, SFMono-Regular, monospace';

// checkbox · CASE/THREAD · MESSAGE (widest scan column) · ISSUE/LOCATION ·
// STATUS (Needle status now nests under the government status, the way the
// category badge nests under ISSUE/LOCATION) · NEXT ACTION · overflow.
const GRID_COLS =
    '34px minmax(150px,1.05fr) minmax(250px,1.7fr) minmax(160px,1.05fr) minmax(230px,1.6fr) minmax(108px,.72fr) 30px';
const GRID_MIN = 962;

// ─── narrow-layout hook (grid → stacked cards below 1024) ─────────────
function useNarrow(bp = 1024) {
    const [narrow, setNarrow] = useState(false);
    useEffect(() => {
        if (typeof window === 'undefined' || !window.matchMedia) return undefined;
        const mq = window.matchMedia(`(max-width: ${bp - 1}px)`);
        const update = () => setNarrow(mq.matches);
        update();
        mq.addEventListener('change', update);
        return () => mq.removeEventListener('change', update);
    }, [bp]);
    return narrow;
}

// ─── formatters ──────────────────────────────────────────────────────
function toDate(v) {
    if (!v) return null;
    const d = v instanceof Date ? v : new Date(v);
    return Number.isNaN(d.getTime()) ? null : d;
}
function fmtDayMonth(v) {
    const d = toDate(v);
    return d ? d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : '';
}
function fmtActivity(v) {
    const d = toDate(v);
    if (!d) return '';
    const time = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }).toLowerCase();
    const today = new Date();
    const isSameDay = (a, b) => a.toDateString() === b.toDateString();
    if (isSameDay(d, today)) return `Today, ${time}`;
    const yst = new Date(today); yst.setDate(today.getDate() - 1);
    if (isSameDay(d, yst)) return `Yesterday, ${time}`;
    return `${d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}, ${time}`;
}

// ─── government status presentation (mirrors Case Detail journey) ─────
const FILED_STATUSES = ['submitted', 'registered', 'forwarded', 'under_review', 'escalated', 'resolved', 'rejected', 'disposed'];
function isGovtFiled(item) {
    if (String(item.govt_reference_number || '').trim()) return true;
    return FILED_STATUSES.includes(String(item.govt_status || '').toLowerCase());
}
function govtPresentation(item) {
    const s = String(item.govt_status || '').toLowerCase();
    const needleStatus = String(item.status || '').toLowerCase();
    const syncState = item.govt_sync_state || null;               // ok | changed | failed | verification | inconclusive
    const ref = String(item.govt_reference_number || '').trim();
    const portal = item.govt_portal_name || item.portal_name || '';
    const lastChecked = item.govt_last_checked_at || null;

    let stage, accent, detail = [];
    if (['resolved', 'disposed'].includes(s)) {
        stage = 'Resolved'; accent = C.green;
    } else if (s === 'rejected') {
        stage = 'Rejected'; accent = C.err;
    } else if (['under_review', 'escalated', 'forwarded'].includes(s)) {
        stage = 'Department Action'; accent = C.green;
    } else if (isGovtFiled(item)) {
        stage = 'Registered with Govt Portal'; accent = C.green;
    } else if (s === 'pending_staff_submit') {
        stage = 'Not Filed'; accent = C.amber; detail = ['Ready for government portal'];
    } else {
        stage = 'Not Filed'; accent = null;
        detail = needleStatus === 'pending_review'
            ? ['Review pending', 'Ready for portal']
            : needleStatus === 'in_progress'
                ? ['Ready for government portal']
                : ['Not filed'];
    }

    const filed = stage !== 'Not Filed';
    const syncFailed = syncState === 'failed' || syncState === 'verification';
    if (syncFailed && filed) accent = C.errAccent;

    return { stage, accent, detail, ref, portal, lastChecked, syncState, syncFailed, filed };
}

// ─── needle status pill ──────────────────────────────────────────────
const NEEDLE_MAP = {
    in_progress:       { label: 'In Progress',   bg: C.needleProgBg,   fg: C.needleProgFg },
    pending_review:    { label: 'Needs Review',  bg: C.needleReviewBg, fg: C.needleReviewFg },
    awaiting_location: { label: 'Needs Location', bg: C.needleReviewBg, fg: C.needleReviewFg },
    new:               { label: 'New',           bg: C.needleProgBg,   fg: C.needleProgFg },
    pending:           { label: 'Pending',       bg: C.needleReviewBg, fg: C.needleReviewFg },
    resolved:          { label: 'Resolved',      bg: C.needleDoneBg,   fg: C.needleDoneFg },
    completed:         { label: 'Resolved',      bg: C.needleDoneBg,   fg: C.needleDoneFg },
    closed:            { label: 'Closed',        bg: C.needleNeutBg,   fg: C.needleNeutFg },
    irrelevant:        { label: 'Closed',        bg: C.needleNeutBg,   fg: C.needleNeutFg },
};
function NeedleStatus({ status }) {
    const m = NEEDLE_MAP[String(status || 'new').toLowerCase()] || NEEDLE_MAP.new;
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center',
            padding: '5px 8px', borderRadius: 5,
            fontSize: 11, fontWeight: 500, background: m.bg, color: m.fg, whiteSpace: 'nowrap',
        }}>
            {m.label}
        </span>
    );
}

// ─── next-action derivation ──────────────────────────────────────────
function nextAction(item) {
    const needle = String(item.status || '').toLowerCase();
    const g = govtPresentation(item);
    if (needle === 'pending_review' || needle === 'awaiting_location') {
        return { label: needle === 'awaiting_location' ? 'Add location' : 'Review case', kind: 'secondary' };
    }
    if (g.syncFailed) return { label: 'Retry sync', kind: 'secondary' };
    if (g.syncState === 'changed') return { label: 'View update', kind: 'secondary' };
    if (!g.filed) {
        if (needle === 'resolved' || needle === 'completed' || needle === 'closed') return null;
        return { label: 'File grievance', kind: 'primary' };
    }
    if (['resolved', 'disposed', 'rejected'].includes(String(item.govt_status || '').toLowerCase())) return null;
    return { label: 'Check status', kind: 'secondary' };
}

// ─── thread / single detection ───────────────────────────────────────
function threadInfo(item) {
    const count = Number(item.thread_case_count || (Array.isArray(item.thread_case_ids) ? item.thread_case_ids.length : 0) || 1);
    const isThread = count > 1;
    const spam = String(item.contact_thread_state || '').toLowerCase() === 'spam_suspected';
    const needsReview = ['pending_review', 'awaiting_location'].includes(String(item.status || '').toLowerCase());
    const g = govtPresentation(item);
    let badgeTone = 'default';
    if (spam || g.syncFailed) badgeTone = 'danger';
    else if (needsReview) badgeTone = 'attention';
    return { count, isThread, badgeTone };
}

function issueTitle(item) {
    return (
        item.problem_subdomain ||
        item.problem_domain ||
        item.category ||
        'Citizen grievance'
    );
}
function shortAssembly(assembly) {
    if (!assembly || assembly === 'Unknown') return '';
    return assembly.replace(/\s*(AC|Assembly Constituency|Assembly)\s*$/i, '').trim();
}
function locationLine(item) {
    const loc = (item.location || '').trim();
    const asm = shortAssembly(item.assembly);
    if (loc && asm && !loc.includes(asm)) return `${loc}, ${asm}`;
    return loc || asm || '—';
}
function languageName(item) {
    const raw = (item.case_metadata?.detected_language || item.case_metadata?.language || item.detected_language || '').trim();
    if (!raw || /unknown/i.test(raw)) return '';
    return raw.charAt(0).toUpperCase() + raw.slice(1);
}

// ─── small UI atoms ──────────────────────────────────────────────────
const badgeBase = {
    padding: '3px 7px', borderRadius: 4, fontSize: 10, fontWeight: 600, letterSpacing: '.025em', whiteSpace: 'nowrap',
};
function ThreadBadge({ isThread, count, tone }) {
    const tones = {
        default:   { bg: C.tintGreen,  fg: C.green },
        attention: { bg: C.tintAmber,  fg: C.rust },
        danger:    { bg: C.tintDanger, fg: C.err },
    };
    const t = tones[tone] || tones.default;
    return (
        <span style={{ ...badgeBase, background: t.bg, color: t.fg }}>
            {isThread ? `THREAD · ${count}` : '1 COMPLAINT'}
        </span>
    );
}

function ActionButton({ action, onClick }) {
    if (!action) return null;
    const primary = action.kind === 'primary';
    return (
        <button
            type="button"
            onClick={onClick}
            style={{
                minHeight: 36, padding: '0 14px', borderRadius: 5,
                fontSize: 12, fontWeight: 500, fontFamily: 'inherit', cursor: 'pointer',
                border: `1px solid ${primary ? C.greenDeep : C.hairSoft}`,
                background: primary ? C.greenDeep : 'transparent',
                color: primary ? '#FFFFFF' : C.greenDeep,
                whiteSpace: 'nowrap',
            }}
        >
            {action.label}
        </button>
    );
}

function OverflowMenu({ item, onSelectCase, onOpenContact, onDeleteCase }) {
    const [open, setOpen] = useState(false);
    useEffect(() => {
        if (!open) return undefined;
        const close = () => setOpen(false);
        window.addEventListener('click', close);
        return () => window.removeEventListener('click', close);
    }, [open]);
    return (
        <div style={{ position: 'relative' }} onClick={(e) => e.stopPropagation()}>
            <button
                type="button"
                aria-label="More actions"
                onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
                style={{
                    width: 26, height: 26, border: 'none', background: 'transparent', cursor: 'pointer',
                    color: C.muted, fontSize: 18, lineHeight: 1, borderRadius: 4,
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                }}
            >
                ⋮
            </button>
            {open && (
                <div style={{
                    position: 'absolute', right: 0, top: 28, zIndex: 20, minWidth: 158,
                    background: C.surface, border: `1px solid ${C.hair}`, borderRadius: 6,
                    boxShadow: '0 4px 14px rgba(33,31,25,0.12)', overflow: 'hidden',
                }}>
                    {[
                        { label: 'Open case', run: () => onSelectCase(item) },
                        onOpenContact && item.user_phone ? { label: 'Contact history', run: () => onOpenContact(item.user_phone) } : null,
                        onDeleteCase ? {
                            label: 'Delete case', danger: true, run: async () => {
                                if (!window.confirm('Delete this case? This cannot be undone.')) return;
                                try { await onDeleteCase(item.id); } catch (err) { console.error('Failed to delete case:', err); }
                            },
                        } : null,
                    ].filter(Boolean).map((opt) => (
                        <button
                            key={opt.label}
                            type="button"
                            onClick={(e) => { e.stopPropagation(); setOpen(false); opt.run(); }}
                            style={{
                                display: 'block', width: '100%', textAlign: 'left', padding: '9px 12px',
                                background: 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                                fontSize: 12.5, color: opt.danger ? C.err : C.ink,
                            }}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

// ─── STATUS cell content ─────────────────────────────────────────────
// Government status on top; the Needle lifecycle status nests below it
// (same pattern as the category badge under ISSUE / LOCATION). The two
// vocabularies stay visually distinct — govt uses the accent bar + stage
// wording, Needle keeps its own tinted pill.
function StatusCellContent({ item }) {
    const g = govtPresentation(item);
    const since = fmtDayMonth(item.updated_at || item.created_at);
    return (
        <div style={{ display: 'flex', gap: 13 }}>
            {g.accent
                ? <div style={{ width: 3, flex: '0 0 3px', borderRadius: 2, background: g.accent }} />
                : <div style={{ width: 7, height: 7, flex: '0 0 7px', marginTop: 5, borderRadius: '50%', background: C.faint }} />}
            <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.ink }}>{g.stage}</div>
                {g.filed && g.portal && (
                    <div style={{ marginTop: 6, fontSize: 12, color: C.muted, lineHeight: 1.35 }}>{g.portal}</div>
                )}
                {g.filed && g.ref && (
                    <div style={{ marginTop: 4, fontSize: 12, color: C.muted, fontFamily: MONO }}>#{g.ref}</div>
                )}
                {!g.filed && g.detail.map((d, i) => (
                    <div key={i} style={{ marginTop: 6, fontSize: 12, color: C.muted, lineHeight: 1.35 }}>{d}</div>
                ))}
                {g.filed && !g.syncFailed && g.lastChecked && (
                    <div style={{ marginTop: 8, fontSize: 11, color: C.muted }}>
                        <span style={{ display: 'inline-block', width: 7, height: 7, marginRight: 7, borderRadius: '50%', background: C.green }} />
                        Last sync: {fmtActivity(g.lastChecked)}
                    </div>
                )}
                {g.syncFailed && (
                    <>
                        <div style={{ marginTop: 6, fontSize: 11, color: C.err }}>● Retry needed</div>
                        <div style={{ marginTop: 5, fontSize: 11, color: C.err }}>
                            ⚠ {g.syncState === 'verification' ? 'Verification needed' : 'Sync failed'}
                        </div>
                    </>
                )}

                <div style={{ marginTop: 12, paddingTop: 10, borderTop: `1px solid ${C.hair}` }}>
                    <NeedleStatus status={item.status} />
                    {since && <div style={{ marginTop: 6, fontSize: 12, color: C.muted }}>Since {since}</div>}
                </div>
            </div>
        </div>
    );
}

// ─── MESSAGE cell — the citizen's raw complaint, verbatim ─────────────
// Source is the case row's own raw_message (the anchor complaint the
// Briefcase already picks as the thread's primary display complaint).
// No AI summary, no quote chrome, no italics, clamped to 3 lines — the
// Case Detail modal exposes the full text.
function MessageCell({ item }) {
    const text = (item.raw_message || '').trim();
    return (
        <div style={{
            fontSize: 13, lineHeight: 1.45, color: C.ink,
            display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
            overflow: 'hidden', wordBreak: 'break-word',
        }}>
            {text || <span style={{ color: C.faint }}>No message content</span>}
        </div>
    );
}

// ─── CASE / THREAD cell content ──────────────────────────────────────
function CaseThreadContent({ item }) {
    const t = threadInfo(item);
    const lang = languageName(item);
    const secondary = t.isThread
        ? `Latest complaint ${formatBriefcaseAge(item.created_at)} ago`
        : `Received ${fmtDayMonth(item.created_at) || '—'}`;
    return (
        <div style={{ display: 'flex', gap: 11, minWidth: 0 }}>
            <div style={{
                flex: '0 0 34px', width: 34, height: 34, borderRadius: 7,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: C.tintGreen, color: C.green,
            }}>
                <BriefcaseIcon name={t.isThread ? 'cluster' : 'briefcase'} size={16} color={C.green} stroke={1.9} />
            </div>
            <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 650, color: C.ink }}>{item.case_ref || `#${item.id}`}</span>
                    <ThreadBadge isThread={t.isThread} count={t.count} tone={t.badgeTone} />
                </div>
                <div style={{ marginTop: 6, fontSize: 12, color: C.muted, lineHeight: 1.35 }}>
                    WhatsApp{!t.isThread && lang ? <> <span style={{ color: C.faint }}>•</span> {lang}</> : null}
                </div>
                <div style={{ marginTop: 6, fontSize: 12, color: C.faint, lineHeight: 1.35 }}>{secondary}</div>
            </div>
        </div>
    );
}

// ─── ISSUE / LOCATION cell content ───────────────────────────────────
function IssueCellContent({ item }) {
    return (
        <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: C.ink, lineHeight: 1.3 }}>{issueTitle(item)}</div>
            <div style={{ marginTop: 6, fontSize: 12, color: C.muted, lineHeight: 1.35 }}>{locationLine(item)}</div>
            {item.category && (
                <span style={{
                    display: 'inline-flex', marginTop: 10, padding: '4px 7px',
                    border: `1px solid ${C.hair}`, borderRadius: 4, background: C.catBg,
                    color: C.muted, fontSize: 11,
                }}>
                    {item.category}
                </span>
            )}
        </div>
    );
}

// ─── checkbox ────────────────────────────────────────────────────────
function Check({ checked, onChange, label }) {
    return (
        <input
            type="checkbox"
            aria-label={label}
            checked={checked}
            onChange={onChange}
            onClick={(e) => e.stopPropagation()}
            style={{ width: 15, height: 15, accentColor: C.green, cursor: 'pointer', margin: 0 }}
        />
    );
}

// ─── skeleton ────────────────────────────────────────────────────────
function SkeletonGrid() {
    return Array.from({ length: 6 }).map((_, i) => (
        <div key={i} style={{ display: 'grid', gridTemplateColumns: GRID_COLS, borderBottom: `1px solid ${C.hair}`, minHeight: 112 }}>
            {Array.from({ length: 7 }).map((__, j) => (
                <div key={j} style={{ padding: '20px 14px' }}>
                    <div style={{ height: 10, width: j === 0 || j === 6 ? 15 : '68%', background: C.hair, opacity: 0.55, borderRadius: 2 }} />
                </div>
            ))}
        </div>
    ));
}

// ─── stacked card (below 1024) ───────────────────────────────────────
function CaseCard({ item, selected, onToggle, onSelectCase, onOpenContact, onDeleteCase }) {
    const action = nextAction(item);
    return (
        <div
            onClick={() => onSelectCase(item)}
            style={{
                borderBottom: `1px solid ${C.hair}`, background: selected ? C.activeTint : 'transparent',
                padding: '16px 16px', cursor: 'pointer',
                display: 'flex', flexDirection: 'column', gap: 12,
            }}
        >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <div style={{ flex: 1, minWidth: 0 }}><CaseThreadContent item={item} /></div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                    <Check checked={selected} onChange={onToggle} label={`Select case ${item.id}`} />
                    <OverflowMenu item={item} onSelectCase={onSelectCase} onOpenContact={onOpenContact} onDeleteCase={onDeleteCase} />
                </div>
            </div>
            <div><div style={metaLbl}>Message</div><MessageCell item={item} /></div>
            <div><div style={metaLbl}>Issue / Location</div><IssueCellContent item={item} /></div>
            <div><div style={metaLbl}>Status</div><StatusCellContent item={item} /></div>
            {action && (
                <div onClick={(e) => e.stopPropagation()}>
                    <ActionButton action={action} onClick={(e) => { e.stopPropagation(); onSelectCase(item); }} />
                </div>
            )}
        </div>
    );
}

const metaLbl = {
    fontSize: 10, fontWeight: 600, letterSpacing: '.05em', textTransform: 'uppercase',
    color: C.faint, marginBottom: 6, fontFamily: MONO,
};

// ─── main ────────────────────────────────────────────────────────────
export default function BriefcaseCasesTable({
    cases,
    loading,
    search,
    statusFilter,
    categoryFilter,
    selectedIds,
    setSelectedIds,
    onSelectCase,
    onOpenContact,
    onDeleteCase,
}) {
    const narrow = useNarrow(1024);
    const [sort, setSort] = useState({ key: null, dir: 'asc' });

    const allSelected = cases.length > 0 && selectedIds.size === cases.length;
    const toggleAll = () => setSelectedIds(allSelected ? new Set() : new Set(cases.map((c) => c.id)));
    const toggleOne = (id) => setSelectedIds((prev) => {
        const next = new Set(prev);
        next.has(id) ? next.delete(id) : next.add(id);
        return next;
    });

    // client-side sort of the current page only (does not refetch; the
    // filter bar's sort control stays authoritative for the full result set)
    const rows = useMemo(() => {
        if (!sort.key) return cases;
        const rank = {
            issue: (c) => issueTitle(c).toLowerCase(),
            govt: (c) => ['not filed', 'rejected', 'registered with govt portal', 'department action', 'resolved']
                .indexOf(govtPresentation(c).stage.toLowerCase()),
        }[sort.key];
        const sorted = [...cases].sort((a, b) => {
            const av = rank(a); const bv = rank(b);
            if (av < bv) return sort.dir === 'asc' ? -1 : 1;
            if (av > bv) return sort.dir === 'asc' ? 1 : -1;
            return 0;
        });
        return sorted;
    }, [cases, sort]);

    const onSort = (key) => setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' }));

    const emptyMsg = (
        <>No cases found
            {categoryFilter ? ` in "${categoryFilter}"` : ''}
            {statusFilter && statusFilter !== 'all_cases' ? ` with status "${statusFilter}"` : ''}
            {search ? ` matching "${search}"` : ''}.</>
    );

    // ── narrow: stacked cards ──
    if (narrow) {
        return (
            <div style={{ background: C.surface, borderTop: `1px solid ${C.hair}`, fontFamily: SANS }}>
                {loading ? (
                    Array.from({ length: 5 }).map((_, i) => (
                        <div key={i} style={{ padding: 16, borderBottom: `1px solid ${C.hair}` }}>
                            <div style={{ height: 12, width: '55%', background: C.hair, opacity: 0.5, borderRadius: 2 }} />
                            <div style={{ height: 10, width: '80%', background: C.hair, opacity: 0.4, borderRadius: 2, marginTop: 12 }} />
                        </div>
                    ))
                ) : rows.length === 0 ? (
                    <div style={{ padding: '48px 20px', textAlign: 'center', color: C.faint, fontSize: 13 }}>{emptyMsg}</div>
                ) : rows.map((item) => (
                    <CaseCard
                        key={item.id}
                        item={item}
                        selected={selectedIds.has(item.id)}
                        onToggle={() => toggleOne(item.id)}
                        onSelectCase={onSelectCase}
                        onOpenContact={onOpenContact}
                        onDeleteCase={onDeleteCase}
                    />
                ))}
            </div>
        );
    }

    // ── desktop / tablet: grid table ──
    const headCell = { display: 'flex', alignItems: 'center', gap: 6, padding: '0 14px', color: C.muted, fontSize: 11, fontWeight: 600, letterSpacing: '.045em' };
    const cellPad = { padding: '17px 14px' };

    const SortIcon = ({ active, dir }) => (
        <span style={{ fontSize: 10, color: active ? C.ink : C.faint, userSelect: 'none' }}>{active ? (dir === 'asc' ? '↑' : '↓') : '↕'}</span>
    );

    return (
        <div style={{ overflowX: 'auto', background: C.surface, borderTop: `1px solid ${C.hair}`, borderBottom: `1px solid ${C.hair}`, fontFamily: SANS }}>
            <div style={{ minWidth: GRID_MIN }}>
                {/* header */}
                <div style={{ display: 'grid', gridTemplateColumns: GRID_COLS, minHeight: 44, alignItems: 'center', borderBottom: `1px solid ${C.hair}` }}>
                    <div style={{ display: 'flex', justifyContent: 'center' }}>
                        <Check checked={allSelected} onChange={toggleAll} label="Select all cases" />
                    </div>
                    <div style={headCell}>CASE / THREAD</div>
                    <div style={headCell}>MESSAGE</div>
                    <div style={{ ...headCell, cursor: 'pointer' }} onClick={() => onSort('issue')}>
                        ISSUE / LOCATION <SortIcon active={sort.key === 'issue'} dir={sort.dir} />
                    </div>
                    <div style={{ ...headCell, cursor: 'pointer' }} onClick={() => onSort('govt')}>
                        STATUS <SortIcon active={sort.key === 'govt'} dir={sort.dir} />
                    </div>
                    <div style={headCell}>NEXT ACTION</div>
                    <div />
                </div>

                {/* body */}
                {loading ? (
                    <SkeletonGrid />
                ) : rows.length === 0 ? (
                    <div style={{ padding: '56px 22px', textAlign: 'center', color: C.faint, fontSize: 13 }}>{emptyMsg}</div>
                ) : rows.map((item) => {
                    const selected = selectedIds.has(item.id);
                    const action = nextAction(item);
                    return (
                        <div
                            key={item.id}
                            onClick={() => onSelectCase(item)}
                            onMouseEnter={(e) => { if (!selected) e.currentTarget.style.background = C.rowHover; }}
                            onMouseLeave={(e) => { if (!selected) e.currentTarget.style.background = 'transparent'; }}
                            style={{
                                display: 'grid', gridTemplateColumns: GRID_COLS, alignItems: 'stretch',
                                borderBottom: `1px solid ${C.hair}`, minHeight: 112, cursor: 'pointer',
                                background: selected ? C.activeTint : 'transparent',
                                boxShadow: item.is_critical ? `inset 3px 0 0 ${C.amber}` : selected ? `inset 3px 0 0 ${C.green}` : 'none',
                                transition: 'background-color 120ms ease',
                            }}
                        >
                            <div style={{ ...cellPad, display: 'flex', justifyContent: 'center', alignItems: 'flex-start' }}>
                                <Check checked={selected} onChange={() => toggleOne(item.id)} label={`Select case ${item.id}`} />
                            </div>
                            <div style={cellPad}><CaseThreadContent item={item} /></div>
                            {/* MESSAGE is vertically centred in the row — a short message
                                sits mid-column, deliberately off the top baseline. */}
                            <div style={{ ...cellPad, display: 'flex', alignItems: 'center' }}><MessageCell item={item} /></div>
                            <div style={cellPad}><IssueCellContent item={item} /></div>
                            <div style={cellPad}><StatusCellContent item={item} /></div>
                            <div style={{ ...cellPad, display: 'flex', alignItems: 'flex-start' }} onClick={(e) => e.stopPropagation()}>
                                <ActionButton action={action} onClick={(e) => { e.stopPropagation(); onSelectCase(item); }} />
                            </div>
                            <div style={{ ...cellPad, display: 'flex', justifyContent: 'center', alignItems: 'flex-start' }}>
                                <OverflowMenu item={item} onSelectCase={onSelectCase} onOpenContact={onOpenContact} onDeleteCase={onDeleteCase} />
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
