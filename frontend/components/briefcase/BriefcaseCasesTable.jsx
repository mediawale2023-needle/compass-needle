'use client';

import { useEffect, useMemo, useState } from 'react';
import { formatBriefcaseAge } from '@/components/briefcase/briefcase-shared';

// ─── Shared Overview / Case Detail visual system ─────────────────────
const C = {
    surface:    '#FFFEFB',
    bg:         '#F3EEE2',
    hair:       '#E4DECB',
    hairStrong: '#C9BFA9',
    hairSoft:   '#DDD6C5',
    ink:        '#211F19',
    muted:      '#6C6858',
    faint:      '#8A8270',
    green:      '#2B6E4C',
    greenDeep:  '#245F45',
    greenSoft:  '#E4EBDD',
    amber:      '#C9821C',
    amberInk:   '#7C5514',
    amberSoft:  '#F2E6CF',
    rust:       '#BC6A36',
    rustInk:    '#8A4A22',
    rustSoft:   '#F1DED0',
    err:        '#A33A32',
    errAccent:  '#A33A32',
    neutralSoft:'#ECE6D8',
    rowHover:   '#FCFAF3',
    activeTint: '#F7F2E7',
    catBg:      '#F8F4EA',
    tintGreen:  'rgba(43,110,76,.08)',
    tintAmber:  'rgba(188,106,54,.12)',
    tintDanger: 'rgba(163,58,50,.10)',
};

const SANS = '"Public Sans", "Noto Sans Devanagari", system-ui, sans-serif';
const MONO = '"IBM Plex Mono", ui-monospace, SFMono-Regular, monospace';

// checkbox · CASE/THREAD · MESSAGE (widest scan column) · ISSUE/LOCATION ·
// STATUS (government primary + short divider + Needle pill & since) ·
// NEXT ACTION · overflow.
const GRID_COLS =
    '34px minmax(116px,0.8fr) minmax(252px,2.4fr) minmax(144px,1fr) minmax(160px,1.18fr) minmax(96px,0.6fr) 30px';
const GRID_MIN = 912;

// ─── narrow-layout hook (grid → stacked cards below the desktop table) ─
function useNarrow(bp = 1200) {
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

// ─── government status presentation (mirrors Case Detail journey) ─────
const FILED_STATUSES = ['submitted', 'registered', 'forwarded', 'under_review', 'escalated', 'resolved', 'rejected', 'disposed'];
function isGovtFiled(item) {
    if (String(item.govt_reference_number || '').trim()) return true;
    return FILED_STATUSES.includes(String(item.govt_status || '').toLowerCase());
}
// STATUS cell = government status (primary) + short divider + Needle pill &
// "since" (secondary). Government stage + AT MOST ONE supporting line; the
// reference number gets its own line only when the case is registered.
// "Ready for government portal" is NEVER inferred from status === in_progress;
// it requires the real govt_status = 'pending_staff_submit'.
function govtPresentation(item) {
    const s = String(item.govt_status || '').toLowerCase();
    const needleStatus = String(item.status || '').toLowerCase();
    const syncState = item.govt_sync_state || null;               // ok | changed | failed | verification | inconclusive
    const ref = String(item.govt_reference_number || '').trim();
    const portal = item.govt_portal_name || item.portal_name || '';
    const syncFailed = syncState === 'failed' || syncState === 'verification';

    let stage = 'NOT FILED';
    let lines = [];
    let tone = null; // null | 'green' | 'err'

    if (['resolved', 'disposed'].includes(s)) {
        stage = 'RESOLVED'; tone = 'green';
        const d = fmtDayMonth(item.resolved_at);
        if (d) lines = [d];
    } else if (s === 'rejected') {
        stage = 'REJECTED'; tone = 'err';
    } else if (syncFailed) {
        stage = 'SYNC ISSUE'; tone = 'err'; lines = ['Check required'];
    } else if (['under_review', 'escalated', 'forwarded'].includes(s)) {
        stage = 'DEPARTMENT ACTION'; tone = 'green';
        if (item.govt_department) lines = [String(item.govt_department)];
    } else if (isGovtFiled(item)) {
        stage = 'REGISTERED WITH GOVT PORTAL'; tone = 'green';
        lines = [portal, ref ? `#${ref}` : ''].filter(Boolean);
    } else if (s === 'pending_staff_submit') {
        stage = 'NOT FILED'; lines = ['Ready for government portal'];
    } else if (needleStatus === 'pending_review') {
        stage = 'NOT FILED'; lines = ['Review pending'];
    } else if (needleStatus === 'awaiting_location') {
        stage = 'NOT FILED'; lines = ['Location needed first'];
    } else {
        stage = 'NOT FILED';
    }

    const filed = !['NOT FILED', 'SYNC ISSUE'].includes(stage) || isGovtFiled(item);
    return { stage, lines, tone, ref, portal, syncState, syncFailed, filed };
}

// ─── Needle status pill — always the real cases.status, approved semantic
// palette only (no blue/purple), and no invented "READY" state. ──────
const NEEDLE_MAP = {
    new:               { label: 'New',                bg: C.neutralSoft, fg: '#544E40' },
    pending_review:    { label: 'Needs Review',       bg: C.rustSoft,    fg: C.rustInk },
    awaiting_location: { label: 'Awaiting Location',  bg: C.amberSoft,   fg: C.amberInk },
    in_progress:       { label: 'In Progress',        bg: C.neutralSoft, fg: '#544E40' },
    pending:           { label: 'Pending',            bg: C.amberSoft,   fg: C.amberInk },
    incomplete:        { label: 'Incomplete',         bg: C.amberSoft,   fg: C.amberInk },
    resolved:          { label: 'Resolved',           bg: '#E0E8DA',     fg: C.greenDeep },
    completed:         { label: 'Resolved',           bg: '#E0E8DA',     fg: C.greenDeep },
    closed:            { label: 'Closed',             bg: C.neutralSoft, fg: C.muted },
    irrelevant:        { label: 'Closed',             bg: C.neutralSoft, fg: C.muted },
    offensive:         { label: 'Closed',             bg: C.neutralSoft, fg: C.muted },
};
function NeedleStatus({ status }) {
    const key = String(status || 'new').toLowerCase();
    const m = NEEDLE_MAP[key] || { label: (status || 'New').replace(/_/g, ' '), bg: C.neutralSoft, fg: C.muted };
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center',
            border: `1px solid ${C.hairStrong}`, padding: '2px 6px',
            fontFamily: MONO, fontSize: 9, fontWeight: 600, letterSpacing: '.03em',
            textTransform: 'uppercase', lineHeight: 1.15,
            background: m.bg, color: m.fg, whiteSpace: 'nowrap',
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
// Restrained, outlined — reads as "step into a workflow", never a filled
// one-click execute, and never out-shouts the citizen's message.
function ActionButton({ action, onClick }) {
    if (!action) return <span style={{ color: C.faint, fontSize: 12 }}>—</span>;
    const strong = action.kind === 'primary';
    return (
        <button
            type="button"
            onClick={onClick}
            style={{
                display: 'inline-flex', alignItems: 'center', gap: 5, maxWidth: '100%',
                minHeight: 28, padding: '5px 9px',
                fontSize: 11, fontWeight: 550, fontFamily: SANS, cursor: 'pointer',
                border: `1px solid ${strong ? 'rgba(43,110,76,0.5)' : C.hairStrong}`,
                background: 'transparent', color: C.greenDeep,
                lineHeight: 1.15, whiteSpace: 'nowrap',
            }}
        >
            {action.label}
            <span style={{ fontFamily: MONO, fontSize: 10, opacity: 0.7 }} aria-hidden="true">→</span>
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

// ─── STATUS cell — two conceptually distinct systems, kept separate but
// compact. Layer A (primary): government stage + AT MOST ONE supporting
// line (+ a #reference line only when registered). Layer B (secondary,
// below a short divider): the real Needle status pill and a "Since" date.
// "Since" is rendered ONLY from cases.status_changed_at — never
// updated_at / created_at / resolved_at / any complaint timestamp. When
// status_changed_at is null the line is omitted.
const GOV_BAR = { green: C.green, err: C.err };
function StatusCellContent({ item }) {
    const g = govtPresentation(item);
    const sinceIso = item.status_changed_at || null;
    const since = sinceIso ? fmtDayMonth(sinceIso) : '';
    return (
        <div style={{ display: 'flex', gap: 9, minWidth: 0 }}>
            <div style={{ flex: '0 0 2px', width: 2, alignSelf: 'stretch', background: GOV_BAR[g.tone] || C.hairStrong }} />
            <div style={{ minWidth: 0 }}>
                <div style={{
                    fontFamily: MONO, fontSize: 10, fontWeight: 700, letterSpacing: '.03em',
                    textTransform: 'uppercase', color: C.ink, lineHeight: 1.2,
                }}>
                    {g.stage}
                </div>
                {g.lines.map((line, i) => (
                    <div
                        key={i}
                        style={{
                            marginTop: i === 0 ? 2 : 1,
                            fontSize: i >= 1 ? 10.5 : 11,
                            fontFamily: i >= 1 ? MONO : SANS,
                            color: g.tone === 'err' ? C.err : (i >= 1 ? C.faint : C.muted),
                            lineHeight: 1.25,
                        }}
                    >
                        {line}
                    </div>
                ))}
                <span style={{ display: 'block', width: 22, height: 1, background: C.hairStrong, margin: '5px 0 4px' }} />
                <NeedleStatus status={item.status} />
                {since && <div style={{ marginTop: 3, fontSize: 10.5, color: C.faint }}>Since {since}</div>}
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
            fontSize: 13, lineHeight: 1.4, color: C.ink,
            display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
            overflow: 'hidden', wordBreak: 'break-word',
        }}>
            {text || <span style={{ color: C.faint }}>No message content</span>}
        </div>
    );
}

// ─── CASE / THREAD cell — compact: ref (+ critical marker), thread/count,
// age. No channel prose, no decorative icon tile. ──────────────────────
function CaseThreadContent({ item }) {
    const t = threadInfo(item);
    const age = formatBriefcaseAge(item.created_at);
    return (
        <div style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, color: C.ink }}>
                    {item.case_ref || `#${item.id}`}
                </span>
                {item.is_critical && (
                    <span
                        title="Critical"
                        style={{
                            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                            width: 14, height: 14, background: C.rust, color: '#F3EEE2',
                            fontSize: 10, fontWeight: 800, lineHeight: 1,
                        }}
                    >
                        !
                    </span>
                )}
            </div>
            <div style={{ marginTop: 5, fontFamily: MONO, fontSize: 10, color: C.muted }}>
                {t.isThread ? `Thread · ${t.count}` : '1 complaint'}
            </div>
            <div style={{ marginTop: 3, fontFamily: MONO, fontSize: 10, color: C.faint }}>{age}</div>
        </div>
    );
}

// ─── ISSUE / LOCATION cell content ───────────────────────────────────
function IssueCellContent({ item }) {
    return (
        <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 12.5, fontWeight: 640, color: C.ink, lineHeight: 1.3 }}>{issueTitle(item)}</div>
            <div style={{ marginTop: 4, fontSize: 11.5, color: C.muted, lineHeight: 1.3 }}>{locationLine(item)}</div>
            {item.category && (
                <span style={{
                    display: 'inline-flex', marginTop: 7, padding: '3px 6px',
                    border: `1px solid ${C.hair}`, background: C.catBg,
                    color: C.muted, fontSize: 10.5,
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
        <div key={i} style={{ display: 'grid', gridTemplateColumns: GRID_COLS, borderBottom: `1px solid ${C.hair}`, minHeight: 100 }}>
            {Array.from({ length: 7 }).map((__, j) => (
                <div key={j} style={{ padding: '14px 14px' }}>
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
    const narrow = useNarrow(1200);
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
    const headCell = { display: 'flex', alignItems: 'center', gap: 6, padding: '0 14px', color: C.faint, fontSize: 9, fontWeight: 600, letterSpacing: '.08em', fontFamily: MONO, textTransform: 'uppercase' };
    const cellPad = { padding: '12px 14px', minWidth: 0 };

    const SortIcon = ({ active, dir }) => (
        <span style={{ fontSize: 10, color: active ? C.ink : C.faint, userSelect: 'none' }}>{active ? (dir === 'asc' ? '↑' : '↓') : '↕'}</span>
    );

    return (
        <div style={{ overflowX: 'auto', background: C.surface, borderTop: `1px solid ${C.hair}`, borderBottom: `1px solid ${C.hair}`, fontFamily: SANS }}>
            <style>{`.bfc-row:focus-visible{outline:2px solid ${C.greenDeep};outline-offset:-2px;}`}</style>
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
                            className="bfc-row"
                            role="button"
                            tabIndex={0}
                            aria-label={`Open case ${item.case_ref || item.id}${item.is_critical ? ' (critical)' : ''}`}
                            onClick={() => onSelectCase(item)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelectCase(item); }
                            }}
                            onMouseEnter={(e) => { if (!selected) e.currentTarget.style.background = C.rowHover; }}
                            onMouseLeave={(e) => { if (!selected) e.currentTarget.style.background = 'transparent'; }}
                            style={{
                                display: 'grid', gridTemplateColumns: GRID_COLS, alignItems: 'start',
                                borderBottom: `1px solid ${C.hair}`, minHeight: 100, cursor: 'pointer',
                                background: selected ? C.activeTint : 'transparent',
                                boxShadow: selected ? `inset 3px 0 0 ${C.green}` : item.is_critical ? `inset 3px 0 0 ${C.rust}` : 'none',
                                transition: 'background-color 120ms ease',
                            }}
                        >
                            <div style={{ ...cellPad, display: 'flex', justifyContent: 'center', alignItems: 'flex-start' }}>
                                <Check checked={selected} onChange={() => toggleOne(item.id)} label={`Select case ${item.id}`} />
                            </div>
                            <div style={cellPad}><CaseThreadContent item={item} /></div>
                            <div style={cellPad}><MessageCell item={item} /></div>
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
