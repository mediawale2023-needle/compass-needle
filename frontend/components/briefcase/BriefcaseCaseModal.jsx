'use client';

import { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Loader2, Send } from 'lucide-react';
import { apiGet, apiPatch, apiPost, apiDelete, API_BASE, getAuthToken } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from '@/components/ui/dropdown-menu';
import BriefcaseSourceMediaViewer from '@/components/briefcase/BriefcaseSourceMediaViewer';
import { STATUS_OPTIONS } from '@/components/briefcase/briefcase-shared';
import { isPrimaryAccount } from '@/lib/account';

const GOVT_FILING_WORKSPACE_SPIKE = process.env.NEXT_PUBLIC_GOVT_FILING_WORKSPACE_SPIKE === 'true';

// ─── Icon component ─────────────────────────────────────────
function Icon({ name, size = 14, color = 'currentColor', stroke = 1.5, filled = false }) {
    const paths = {
        x:        <><path d="M6 6l12 12M18 6L6 18" /></>,
        chevL:    <><path d="M15 6l-6 6 6 6" /></>,
        chevR:    <><path d="M9 6l6 6-6 6" /></>,
        chevD:    <><path d="M6 9l6 6 6-6" /></>,
        sparkle:  <><path d="M12 3v6M12 15v6M3 12h6M15 12h6M6 6l4 4M14 14l4 4M6 18l4-4M14 10l4-4" /></>,
        play:     <><path d="M7 5l12 7-12 7z" fill="currentColor" /></>,
        phone:    <><path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z" /></>,
        pin:      <><path d="M12 21s7-7 7-12a7 7 0 10-14 0c0 5 7 12 7 12z" /><circle cx="12" cy="9" r="2.5" /></>,
        clock:    <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
        check:    <><path d="M5 12l5 5 9-11" /></>,
        edit:     <><path d="M4 19l4-1 12-12-3-3L5 15z" /><path d="M14 6l3 3" /></>,
        whatsapp: <><circle cx="12" cy="12" r="9" /><path d="M16 14a4 4 0 01-5 1l-3 1 1-3a4 4 0 116-7" /></>,
        warn:     <><path d="M12 3l10 17H2z" /><path d="M12 10v5M12 18v.5" /></>,
        eye:      <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></>,
        dots:     <><circle cx="6" cy="12" r="1.5" fill="currentColor" /><circle cx="12" cy="12" r="1.5" fill="currentColor" /><circle cx="18" cy="12" r="1.5" fill="currentColor" /></>,
        download: <><path d="M12 4v12M6 12l6 6 6-6M5 20h14" /></>,
        history:  <><path d="M3 12a9 9 0 109-9M3 3v6h6" /><path d="M12 7v5l3 2" /></>,
        send:     <><path d="M4 12l16-7-7 16-2-7z" /></>,
        bolt:     <><path d="M13 2L4 14h7l-2 8 9-12h-7z" /></>,
        cluster:  <><circle cx="7" cy="7" r="3" /><circle cx="17" cy="8" r="2.5" /><circle cx="9" cy="17" r="2.5" /><circle cx="18" cy="16" r="2.5" /><path d="M7 7l10 1M9 17l9-1M7 7l2 10" /></>,
        user:     <><circle cx="12" cy="9" r="4" /><path d="M4 21c0-5 4-7 8-7s8 2 8 7" /></>,
        trash:    <><path d="M4 6h16M9 6V4h6v2M5 6l1 14h12l1-14" /></>,
        external: <><path d="M14 4h6v6M20 4L10 14" /><path d="M8 5H5a1 1 0 00-1 1v13a1 1 0 001 1h13a1 1 0 001-1v-3" /></>,
        lock:     <><rect x="5" y="10" width="14" height="10" rx="1.5" /><path d="M8 10V7a4 4 0 018 0v3" /></>,
        unlock:   <><rect x="5" y="10" width="14" height="10" rx="1.5" /><path d="M8 10V7a4 4 0 017.5-1.5" /></>,
        plus:     <><path d="M12 5v14M5 12h14" /></>,
        doc:      <><path d="M7 3h7l4 4v13a1 1 0 01-1 1H7a1 1 0 01-1-1V4a1 1 0 011-1z" /><path d="M14 3v4h4" /></>,
        chat:     <><path d="M4 5h16a1 1 0 011 1v10a1 1 0 01-1 1H10l-4 4v-4H4a1 1 0 01-1-1V6a1 1 0 011-1z" /></>,
        star:     <><path d="M12 3l2.7 5.9 6.3.7-4.8 4.3 1.4 6.2L12 17l-5.6 3.1 1.4-6.2-4.8-4.3 6.3-.7z" /></>,
    };
    return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill={filled ? color : "none"}
            stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round">
            {paths[name] || null}
        </svg>
    );
}

// ─── Shared design tokens ────────────────────────────────────
const C = {
    paper:       '#F2EBD9',
    paperDeep:   '#E8E0CB',
    surface:     '#F7F2E6',
    surfaceWarm: '#F7F0DC',
    ink:         '#1A1812',
    ink2:        '#4A453A',
    ink3:        '#7A7263',
    hair:        'rgba(26,24,18,0.14)',
    hairStrong:  'rgba(26,24,18,0.32)',
    green:       '#006A4D',
    greenDeep:   '#003B2A',
    greenInk:    '#024A36',
    greenTint:   '#DFE9E2',
    greenWash:   '#EAF1EC',
    saffron:     '#C76A1A',
    saffronTint: '#F4E3CE',
    red:         '#C0392B',
};

const sec = {
    padding: '14px 20px',
    borderBottom: `1px solid ${C.hair}`,
    background: C.paper,
};

const monoLbl = {
    fontFamily: '"JetBrains Mono", monospace',
    fontSize: 9.5,
    letterSpacing: '0.16em',
    color: C.ink3,
    textTransform: 'uppercase',
    marginBottom: 8,
    display: 'block',
};

// Right-rail rows inherit the sidebar's own warm background instead of
// repainting a contrasting card per row — this is what makes the sidebar
// read as one continuous operational panel instead of stacked mini-forms.
const asideSec = {
    padding: '14px 20px',
    borderBottom: `1px solid ${C.hair}`,
};

const CASE_DETAIL_SIDEBAR_WIDTH = 'clamp(320px, 27vw, 594px)';

// ─── Mobile breakpoint hook (matches Tailwind `sm`) ──────────
function useIsMobile(breakpoint = 640) {
    const [isMobile, setIsMobile] = useState(false);
    useEffect(() => {
        if (typeof window === 'undefined' || !window.matchMedia) return undefined;
        const mq = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
        const update = () => setIsMobile(mq.matches);
        update();
        mq.addEventListener('change', update);
        return () => mq.removeEventListener('change', update);
    }, [breakpoint]);
    return isMobile;
}

function normalizeForComparison(text) {
    return String(text || '').replace(/\s+/g, ' ').trim().toLowerCase();
}

function isMeaningfullyDistinctSummary(summary, rawMessage) {
    if (!summary) return false;
    const normalizedSummary = normalizeForComparison(summary);
    const normalizedRaw = normalizeForComparison(rawMessage);
    if (!normalizedSummary) return false;
    if (!normalizedRaw) return true;
    return normalizedSummary !== normalizedRaw;
}

function buildStructuredSummary(current, meta) {
    const category = meta.ai_category || current.problem_domain || current.category || '';
    const subcategory = meta.ai_subcategory || current.problem_subdomain || '';
    const location = meta.matched_value || current.location || '';
    const assembly = meta.assembly_constituency || current.assembly || '';
    const person = meta.person || '';
    const department = meta.department || '';
    const scheme = meta.scheme || '';
    const fragments = [];

    if (category && !/^(uncategorised|general)$/i.test(category)) {
        fragments.push(subcategory ? `${category} · ${subcategory}` : category);
    }
    if (location) fragments.push(`location ${location}`);
    if (assembly) fragments.push(`assembly ${assembly}`);
    if (person) fragments.push(`mentions ${person}`);
    if (department) fragments.push(`department ${department}`);
    if (scheme) fragments.push(`scheme ${scheme}`);

    if (!fragments.length) return '';
    return `Case classified as ${fragments.join(' · ')}.`;
}

function getCaseSummary(current, meta) {
    if (isMeaningfullyDistinctSummary(meta.summary, current.raw_message)) {
        return meta.summary;
    }
    return buildStructuredSummary(current, meta);
}

function getSuggestedTriage(meta, current) {
    const aiCategory = meta.ai_category || current.problem_domain || '';
    const aiSubcategory = meta.ai_subcategory || current.problem_subdomain || '';
    const detectedLanguage = meta.detected_language || meta.language || '';

    if (!aiCategory || /^(uncategorised|general)$/i.test(aiCategory)) {
        return null;
    }

    return {
        ai_category: aiCategory,
        ai_subcategory: aiSubcategory,
        detected_language: detectedLanguage,
    };
}

// Mirrors the backend triggers for status='pending_review':
// - main.py _REVIEW_REQUIRED_CATEGORIES (category gate, unconditional)
// - modules/whatsapp_geography.py _LOW_CONFIDENCE_LEVELS (geo confidence gate)
// A case can hit either (or both) while every visible field is fully populated,
// so the reason has to be spelled out here rather than inferred from the data.
const REVIEW_REQUIRED_CATEGORIES = new Set(['law & order', 'law and order', 'emergency', 'political', 'legal']);
const LOW_CONFIDENCE_GEO_LEVELS = new Set(['fuzzy', 'speech_phonetic']);

function getReviewReasons(current, meta) {
    const reasons = [];
    const categoryLower = String(current.category || '').toLowerCase().trim();

    if (REVIEW_REQUIRED_CATEGORIES.has(categoryLower)) {
        reasons.push({
            title: `"${current.category}" always requires manual review`,
            detail: 'This category is held for staff review before any reply goes out to the citizen — regardless of how complete the rest of the case is.',
        });
    }

    const geoConfidence = String(meta.geography_confidence || '').toLowerCase();
    if (meta.needs_geography_review || LOW_CONFIDENCE_GEO_LEVELS.has(geoConfidence)) {
        const location = meta.matched_value || current.location || 'the detected location';
        reasons.push({
            title: `Location matched at low confidence${geoConfidence ? ` (${geoConfidence})` : ''}`,
            detail: `"${location}" was matched by a ${geoConfidence === 'speech_phonetic' ? 'phonetic/voice-note' : 'fuzzy'} guess, not an exact or alias match. Confirm it's correct, or edit it in Geography and save — that clears this flag.`,
        });
    }

    const isUncategorisedCase = !current.category || current.category === 'Uncategorised' || current.category === 'General';
    if (isUncategorisedCase && reasons.length === 0) {
        reasons.push({
            title: 'Category could not be confidently determined',
            detail: 'No deterministic rule or keyword confirmed the AI\'s category guess. Pick a category to continue.',
        });
    }

    if (reasons.length === 0) {
        reasons.push({
            title: 'Flagged for review',
            detail: 'This case was held for manual review by the intake pipeline. Check geography and category, then update the status once confirmed.',
        });
    }

    return reasons;
}

// ─── Needs-review reason banner ────────────────────────────────
function ReviewReasonBanner({ current, meta, onViewSummary }) {
    const reasons = getReviewReasons(current, meta);
    return (
        <div style={{
            margin: '14px 20px 0', padding: '14px 16px',
            background: C.saffronTint,
            border: `1px solid ${C.saffron}`,
        }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
                    <Icon name="warn" size={13} color={C.saffron} stroke={2} />
                    <span style={{
                        fontFamily: '"JetBrains Mono", monospace', fontSize: 9.5,
                        letterSpacing: '0.16em', color: C.saffron, textTransform: 'uppercase', fontWeight: 700,
                    }}>Needs review · why</span>
                </span>
                {onViewSummary && (
                    <button type="button" onClick={onViewSummary} style={{
                        padding: '6px 12px', background: C.surface, border: `1px solid ${C.hairStrong}`, color: C.ink,
                        fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
                    }}>
                        View AI summary
                    </button>
                )}
            </div>
            <div style={{ fontSize: 13.5, fontWeight: 700, color: C.ink, marginBottom: 6 }}>Flagged for review</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {reasons.map((reason, i) => (
                    <div key={i}>
                        {reasons.length > 1 && <div style={{ fontSize: 13, fontWeight: 600, color: C.ink }}>{reason.title}</div>}
                        <div style={{ fontSize: 12.5, color: C.ink2, lineHeight: 1.55, marginTop: 2 }}>{reason.detail}</div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ─── Numbered section heading (Citizen complaint → AI understanding →
// Attachments → Government filing — the fixed provenance order for a
// complaint, per complaint) ───────────────────────────────────
function SectionHeading({ n, label, trailing, info }) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            {n != null && (
                <span style={{
                    width: 18, height: 18, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: C.ink, color: C.paper, fontSize: 10, fontWeight: 700,
                    fontFamily: '"JetBrains Mono", monospace',
                }}>{n}</span>
            )}
            <span style={{ ...monoLbl, marginBottom: 0 }}>{label}</span>
            {info && (
                <span title={info} style={{
                    width: 14, height: 14, borderRadius: '50%', border: `1px solid ${C.ink3}`,
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 9, fontFamily: '"JetBrains Mono", monospace', color: C.ink3, flexShrink: 0,
                }}>i</span>
            )}
            <span style={{ flex: 1 }} />
            {trailing}
        </div>
    );
}

function CaseDetailDesignSidebar() {
    const navItems = [
        ['Overview'],
        ['Briefcase', '99+', true],
        ['Letterbox', '3'],
        ['Drafter'],
        ['Archives'],
    ];

    return (
        <aside style={{
            width: CASE_DETAIL_SIDEBAR_WIDTH,
            flex: '0 0 auto',
            minHeight: '100vh',
            background: '#11110B',
            color: '#F6F0DD',
            padding: '60px 34px 34px',
            display: 'flex',
            flexDirection: 'column',
            fontFamily: '"Inter", "Noto Sans Devanagari", system-ui, sans-serif',
        }}>
            <div style={{
                width: 88, height: 88, borderRadius: 22,
                background: '#F6F0DD', color: '#11110B',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: 42,
            }}>
                <Icon name="clock" size={36} color="#11110B" stroke={2.1} />
            </div>
            <div style={{
                fontFamily: '"Source Serif 4", Georgia, serif',
                fontWeight: 800,
                fontSize: 50,
                lineHeight: 0.98,
                letterSpacing: '-0.035em',
                marginBottom: 28,
            }}>
                <div>Compass</div>
                <div>Needle</div>
            </div>
            <div style={{
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: 17,
                letterSpacing: '0.24em',
                textTransform: 'uppercase',
                color: 'rgba(246,240,221,0.55)',
                marginBottom: 88,
            }}>
                V3 · Operations
            </div>
            <div style={{
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: 17,
                letterSpacing: '0.24em',
                textTransform: 'uppercase',
                color: 'rgba(246,240,221,0.45)',
                marginBottom: 30,
            }}>
                Modules
            </div>
            <nav style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {navItems.map(([label, badge, active]) => (
                    <div key={label} style={{
                        height: 76,
                        borderRadius: 13,
                        background: active ? 'rgba(82,67,42,0.42)' : 'transparent',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: active ? '0 26px' : '0 5px',
                        color: active ? '#F6F0DD' : 'rgba(246,240,221,0.72)',
                        fontSize: 33,
                        fontWeight: active ? 800 : 500,
                        letterSpacing: '-0.035em',
                    }}>
                        <span>{label}</span>
                        {badge && (
                            <span style={{
                                minWidth: active ? 83 : 52,
                                height: active ? 43 : 43,
                                borderRadius: 999,
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                padding: '0 16px',
                                background: active ? '#C46B32' : 'rgba(246,240,221,0.14)',
                                color: active ? '#FFF6E2' : 'rgba(246,240,221,0.72)',
                                fontSize: active ? 24 : 22,
                                fontWeight: 900,
                            }}>
                                {badge}
                            </span>
                        )}
                    </div>
                ))}
            </nav>
            <div style={{ marginTop: 'auto' }}>
                <div style={{
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: 17,
                    letterSpacing: '0.24em',
                    textTransform: 'uppercase',
                    color: 'rgba(246,240,221,0.42)',
                    marginBottom: 30,
                }}>
                    System
                </div>
                <div style={{ fontSize: 33, color: 'rgba(246,240,221,0.75)', fontWeight: 500 }}>
                    Settings
                </div>
            </div>
        </aside>
    );
}

// ─── Drawer header ───────────────────────────────────────────
// "Back" closes the drawer (there's no separate case-list page underneath
// to navigate to — the Sheet overlays the Briefcase list, so closing it
// is going back to the Briefcase).
function StatusPill({ status, tone = 'default' }) {
    const normalized = String(status || 'new').toLowerCase();
    const labels = {
        pending: 'Pending',
        pending_review: 'Pending Review',
        awaiting_location: 'Awaiting Location',
        new: 'New',
        in_progress: 'In Progress',
        resolved: 'Resolved',
        completed: 'Completed',
        closed: 'Closed',
        critical: 'Critical',
    };
    const palette = {
        pending: { fg: C.saffron, bg: C.saffronTint, dot: C.saffron },
        pending_review: { fg: C.saffron, bg: C.saffronTint, dot: C.saffron },
        awaiting_location: { fg: C.saffron, bg: C.saffronTint, dot: C.saffron },
        new: { fg: C.greenInk, bg: C.greenWash, dot: C.green },
        in_progress: { fg: '#795008', bg: '#F3E7C8', dot: C.saffron },
        resolved: { fg: C.greenInk, bg: C.greenTint, dot: C.green },
        completed: { fg: C.greenInk, bg: C.greenTint, dot: C.green },
        closed: { fg: C.ink3, bg: C.paperDeep, dot: C.ink3 },
        critical: { fg: C.red, bg: '#FDEDEC', dot: C.red },
    }[normalized] || { fg: C.ink2, bg: C.paperDeep, dot: C.ink3 };

    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap',
            padding: tone === 'small' ? '6px 16px' : '14px 33px',
            borderRadius: 999, border: `1px solid ${palette.bg}`,
            background: palette.bg, color: palette.fg,
            fontSize: tone === 'small' ? 20 : 29, fontWeight: 800,
            fontFamily: tone === 'small' ? '"Inter", sans-serif' : '"Inter", "Noto Sans Devanagari", system-ui, sans-serif',
            letterSpacing: tone === 'small' ? '-0.03em' : '-0.035em',
        }}>
            <span style={{ width: tone === 'small' ? 10 : 14, height: tone === 'small' ? 10 : 14, borderRadius: '50%', background: palette.dot, flexShrink: 0 }} />
            {labels[normalized] || String(status || 'new').replace(/_/g, ' ')}
        </span>
    );
}

// ─── Drawer header ───────────────────────────────────────────
// "Back" closes the drawer. The surface is styled as the main console pane
// from the PDF, while keeping every existing action wired to the same handlers.
function DrawerHeader({ caseRef, status, isUncategorised, onClose, isFollowing, onToggleFollow, followBusy, onCopyRef }) {
    const normalizedStatus = String(status || 'new').toLowerCase();

    return (
        <div style={{
            flexShrink: 0,
            background: C.paper, borderBottom: `1px solid ${C.hair}`,
            display: 'flex', alignItems: 'center', gap: 14,
            padding: '0 76px',
            height: 190,
        }}>
            <button onClick={onClose} style={{
                border: `1px solid ${C.hair}`, borderRadius: 18, background: C.surface, cursor: 'pointer', flexShrink: 0,
                display: 'flex', alignItems: 'center', gap: 16, padding: '18px 36px',
                fontFamily: 'inherit', fontSize: 26, fontWeight: 600, color: C.ink2,
                outline: 'none',
            }}>
                <Icon name="chevL" size={25} color={C.ink2} stroke={2} /> Back to Briefcase
            </button>

            <span style={{ width: 1, height: 60, background: C.hair, margin: '0 30px 0 22px', flexShrink: 0 }} />

            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 26, minWidth: 0 }}>
                <span style={{
                    fontFamily: '"Source Serif 4", Georgia, serif',
                    fontSize: 52, lineHeight: 1, fontWeight: 800, color: C.ink, whiteSpace: 'nowrap',
                    letterSpacing: '-0.04em',
                }}>
                    Case {caseRef}
                </span>
                <span style={{
                    padding: '13px 26px', borderRadius: 999, border: `1px solid ${C.hair}`,
                    color: C.ink3, background: C.surface, fontSize: 19,
                    fontFamily: '"JetBrains Mono", monospace', letterSpacing: '0.14em', textTransform: 'uppercase',
                }}>
                    Record open
                </span>
                <Icon name="chevR" size={28} color={C.ink3} stroke={2} />
                <StatusPill status={normalizedStatus} />

                {isUncategorised && (
                    <span style={{
                        padding: '9px 18px', borderRadius: 999, background: C.saffronTint, color: C.saffron,
                        fontSize: 13, fontWeight: 800, letterSpacing: '0.08em', textTransform: 'uppercase',
                        border: `1px solid ${C.saffronTint}`, whiteSpace: 'nowrap',
                    }}>uncategorised</span>
                )}
            </div>

            <div style={{ display: 'flex', gap: 12, flexShrink: 0 }}>
                <button
                    onClick={onToggleFollow}
                    disabled={followBusy}
                    style={{
                        width: 48, height: 48, borderRadius: 13, border: `1px solid ${isFollowing ? C.green : C.hair}`,
                        background: C.surface, cursor: followBusy ? 'not-allowed' : 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        opacity: followBusy ? 0.6 : 1,
                    }}
                    title={isFollowing ? 'Following - click to unfollow' : 'Follow this case'}
                >
                    <Icon name="star" size={23} color={isFollowing ? C.green : C.ink2} filled={isFollowing} />
                </button>
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <button style={{
                            width: 48, height: 48, borderRadius: 13, border: `1px solid ${C.hair}`,
                            background: C.surface, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }} title="More options">
                            <Icon name="dots" size={24} color={C.ink2} />
                        </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" style={{ fontFamily: 'inherit' }}>
                        <DropdownMenuItem onClick={onCopyRef}>
                            <Icon name="doc" size={12} color={C.ink2} style={{ marginRight: 8 }} />
                            Copy case reference
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </div>
    );
}

// ─── Case meta row (case-level: WhatsApp/language pills + received date —
// shared by every complaint in the thread, doesn't change on tab switch) ──
function formatShortDate(value) {
    if (!value) return '';
    const d = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

function inferCaseDisplayTitle(current, meta) {
    if (meta.issue_title || meta.summary_title || current.case_title) {
        return meta.issue_title || meta.summary_title || current.case_title;
    }
    const text = `${current.raw_message || ''} ${meta.summary || ''}`.toLowerCase();
    const location = meta.matched_value || current.location || '';
    if (location && /\bpotholes?\b|\bgadd?ha\b|\bkhadda\b|\bpits?\b/.test(text)) {
        return `Potholes in ${location}`;
    }
    if (location && /\bwater\b|\bpaani\b|\bneer\b|\bjal\b/.test(text)) {
        return `Water issue in ${location}`;
    }
    if (location && /\bgarbage\b|\bwaste\b|\bkachra\b/.test(text)) {
        return `Garbage issue in ${location}`;
    }
    if (location && /\bdrain|sewer|nala|naali\b/.test(text)) {
        return `Drainage issue in ${location}`;
    }
    const category = current.problem_subdomain || current.problem_domain || current.category;
    return location && category ? `${category} in ${location}` : category || 'Citizen grievance';
}

function CaseMetaRow({ phone, createdAt, language }) {
    const dateStr = createdAt
        ? createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
        : '–';
    const timeStr = createdAt
        ? createdAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) + ' IST'
        : '–';
    return (
        <div style={{
            height: 94,
            padding: '0 76px',
            display: 'flex',
            alignItems: 'center',
            gap: 26,
            borderBottom: `1px solid ${C.hair}`,
            background: C.paper,
            overflow: 'hidden',
        }}>
            <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 18,
                fontSize: 29, color: C.ink2, fontWeight: 700,
                whiteSpace: 'nowrap',
            }}>
                <Icon name="whatsapp" size={31} color="#1BA96D" stroke={1.8} />
                WhatsApp
            </span>
            {language && (
                <>
                    <span style={{ color: C.hair, fontSize: 22 }}>·</span>
                    <span style={{ fontSize: 29, color: C.ink2, fontWeight: 700, whiteSpace: 'nowrap' }}>{language}</span>
                </>
            )}
            {phone && (
                <>
                    <span style={{ color: C.hair, fontSize: 22 }}>·</span>
                    <span style={{ fontSize: 29, color: C.ink2, fontWeight: 700, letterSpacing: '0.12em', whiteSpace: 'nowrap' }}>...{phone.slice(-4)}</span>
                </>
            )}
            <span style={{ color: C.hair, fontSize: 22 }}>·</span>
            <span style={{ fontSize: 29, color: C.ink2, fontWeight: 700, whiteSpace: 'nowrap' }}>Received {dateStr}, {timeStr}</span>
        </div>
    );
}

function CaseHero({ current, meta, priority, onPriorityChange }) {
    const category = current.problem_subdomain || current.problem_domain || current.category || 'Uncategorised';
    const location = meta.matched_value || current.location || 'Location unknown';
    const assembly = current.assembly || meta.assembly_constituency || '';
    const priorityLabel = {
        critical: 'Critical priority',
        high: 'High priority',
        low: 'Low priority',
        standard: 'Standard priority',
    }[priority || 'standard'] || 'Standard priority';
    const title = inferCaseDisplayTitle(current, meta);

    return (
        <div style={{ padding: '48px 76px 40px', background: C.paper }}>
            <h1 style={{
                margin: 0, fontFamily: '"Source Serif 4", Georgia, serif',
                fontSize: 51, lineHeight: 1.08, fontWeight: 800, color: C.ink,
                letterSpacing: '-0.045em',
            }}>
                {title}
            </h1>
            <div style={{ marginTop: 28, display: 'flex', alignItems: 'center', gap: 18, flexWrap: 'nowrap', overflow: 'hidden' }}>
                <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '14px 28px', borderRadius: 999, background: '#FFFDF7',
                    border: `1px solid ${C.hair}`, color: C.ink2,
                    fontSize: 27, fontWeight: 700, whiteSpace: 'nowrap',
                }}>
                    <Icon name="doc" size={28} color={C.ink3} /> {category}
                </span>
                <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '14px 28px', borderRadius: 999, background: '#FFFDF7',
                    border: `1px solid ${C.hair}`, color: C.ink2,
                    fontSize: 27, fontWeight: 700, whiteSpace: 'nowrap',
                }}>
                    <Icon name="pin" size={28} color={C.ink3} /> {location}
                </span>
                {assembly && (
                    <span style={{
                        padding: '14px 28px', borderRadius: 999, background: '#FFFDF7',
                        border: `1px solid ${C.hair}`, color: C.ink2,
                        fontSize: 27, fontWeight: 700, whiteSpace: 'nowrap',
                    }}>
                        {assembly}
                    </span>
                )}
                <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '12px 26px', borderRadius: 999, background: C.paper,
                    border: `2px solid ${C.ink3}`, color: C.ink2,
                    fontSize: 27, fontWeight: 800, whiteSpace: 'nowrap',
                }}>
                    <select value={priority || 'standard'} onChange={(e) => onPriorityChange(e.target.value)} style={{
                        border: 'none', background: 'transparent', padding: 0,
                        color: C.ink2, fontSize: 27, fontWeight: 800, fontFamily: 'inherit', outline: 'none',
                    }}>
                        <option value="critical">Critical priority</option>
                        <option value="high">High priority</option>
                        <option value="standard">Standard priority</option>
                        <option value="low">Low priority</option>
                    </select>
                </span>
                {priority !== 'standard' && (
                    <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: 5,
                        padding: '14px 28px', borderRadius: 999, color: C.greenInk,
                        fontSize: 27, fontWeight: 700, whiteSpace: 'nowrap',
                    }}>
                        <Icon name="star" size={28} color={C.greenInk} filled /> {priorityLabel}
                    </span>
                )}
            </div>
        </div>
    );
}

// ─── Contact-level triage notice (messages the intake pipeline has seen
// from this same phone number but not yet promoted into their own
// complaint — this is thread/case-level, not tied to whichever complaint
// tab is currently selected) ─────────────────────────────────────
function ContactQueueNotice({ current }) {
    const bufferedItems = Array.isArray(current?.pending_contact_messages) ? current.pending_contact_messages : [];
    const suppressedItems = Array.isArray(current?.suppressed_contact_messages) ? current.suppressed_contact_messages : [];
    const contactThreadState = current?.contact_thread_state || 'normal';
    const distinctIssueCount = Number(current?.distinct_issue_count || 0);

    if (bufferedItems.length === 0 && suppressedItems.length === 0) {
        return null;
    }

    const stateTone = {
        high_frequency: { fg: C.saffron, bg: C.saffronTint, label: 'High frequency contact' },
        spam_suspected: { fg: C.red, bg: '#FDEDEC', label: 'Spam suspected' },
    }[String(contactThreadState).toLowerCase()];

    return (
        <div style={sec}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
                <span style={monoLbl}>Other messages from this contact · not yet a complaint</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    {distinctIssueCount > 0 && (
                        <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.ink3, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                            {distinctIssueCount} issue{distinctIssueCount === 1 ? '' : 's'} tracked
                        </span>
                    )}
                    {stateTone && (
                        <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 8px',
                            background: stateTone.bg, color: stateTone.fg, fontSize: 10, fontWeight: 700,
                            letterSpacing: '0.04em', textTransform: 'uppercase',
                        }}>
                            <Icon name={contactThreadState === 'spam_suspected' ? 'warn' : 'clock'} size={10} color={stateTone.fg} stroke={2} />
                            {stateTone.label}
                        </span>
                    )}
                </div>
            </div>
            <div style={{ fontSize: 11, color: C.ink2, marginBottom: 10, lineHeight: 1.5 }}>
                The AI intake pipeline flagged these as possibly separate from any complaint above, but hasn't promoted them into their own complaint yet.
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {bufferedItems.map((item) => (
                    <div key={item.id} style={{ border: `1px solid ${C.greenTint}`, background: C.greenWash, padding: '10px 12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
                            <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.greenInk, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                                Possibly distinct issue
                            </span>
                            <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.ink3 }}>
                                {item.created_at ? new Date(item.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''}
                            </span>
                        </div>
                        <div style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.55 }}>{item.raw_message || '—'}</div>
                        {(item.problem_subdomain || item.problem_domain) && (
                            <div style={{ marginTop: 8, fontSize: 11, color: C.ink2 }}>{item.problem_subdomain || item.problem_domain}</div>
                        )}
                    </div>
                ))}
                {suppressedItems.map((item, idx) => (
                    <div key={`suppressed-${idx}`} style={{ border: `1px solid ${C.red}`, background: '#FEF3F2', padding: '10px 12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
                            <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.red, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                                Suppressed after spam threshold
                            </span>
                            <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.ink3 }}>
                                {item.created_at ? new Date(item.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''}
                            </span>
                        </div>
                        <div style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.55 }}>{item.message || '—'}</div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ─── Complaint tab strip ─────────────────────────────────────
// A citizen can raise more than one distinct grievance in the same WhatsApp
// thread. Each is its own Case row on the backend (own status, own
// assignment, own government filing) — this strip is the primary navigation
// between them. Numbering is chronological (oldest = Complaint 1) so it
// stays stable as new complaints are added to the thread.
// Complaints are produced only by the citizen intake / AI pipeline — staff
// review, respond to, escalate and resolve them, but never create one by
// hand, so there is deliberately no "add complaint" control here.
function ComplaintTabStrip({ threadCases, activeCaseId, onSelectCase }) {
    const ordered = [...threadCases].slice().reverse();
    return (
        <div style={{ padding: '42px 76px 0', background: C.paper, borderTop: `1px solid ${C.hair}`, borderBottom: `1px solid ${C.hair}` }}>
            <div style={{
                marginBottom: 30, display: 'flex', alignItems: 'center', gap: 18,
                color: C.ink3, fontFamily: '"JetBrains Mono", monospace',
                fontSize: 26, letterSpacing: '0.15em', textTransform: 'uppercase',
                fontWeight: 800,
            }}>
                <span>Complaints in this case</span>
                <span>({ordered.length} · Same location, 6 weeks)</span>
            </div>
            <div style={{ display: 'flex', gap: 22, overflowX: 'auto', paddingBottom: 42 }}>
                {ordered.map((item, idx) => {
                    const isActive = item.id === activeCaseId;
                    return (
                        <button
                            key={item.id}
                            type="button"
                            onClick={() => onSelectCase(item)}
                            style={{
                                position: 'relative', padding: '32px 38px 26px', flexShrink: 0, textAlign: 'left',
                                width: 410, height: 220,
                                borderRadius: 20,
                                border: `2px solid ${isActive ? C.ink : C.hair}`,
                                background: isActive ? '#FFFDF7' : C.paper,
                                color: C.ink,
                                cursor: 'pointer', fontFamily: 'inherit',
                                display: 'flex', flexDirection: 'column', gap: 18,
                                boxShadow: 'none',
                            }}
                        >
                            <span style={{
                                fontSize: 25, color: C.ink3, fontFamily: '"JetBrains Mono", monospace',
                                textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 700,
                            }}>
                                Complaint {idx + 1}
                            </span>
                            <span style={{ fontSize: 36, color: C.ink, fontWeight: 900, letterSpacing: '-0.05em', lineHeight: 1 }}>
                                {formatShortDate(item.created_at) || 'No date'}
                            </span>
                            <StatusPill status={item.status || 'new'} tone="small" />
                            {isActive && (
                                <span style={{ position: 'absolute', top: 34, right: 36 }}>
                                    <Icon name="check" size={28} color={C.saffron} stroke={2.5} />
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}

// ─── 1 · Citizen complaint ────────────────────────────────────
// The citizen's own words are the source of truth. This never shows AI text
// in place of what the citizen actually sent — translation/summary live in
// the AI Understanding section below, clearly labelled as AI-generated.
function CitizenComplaintSection({ current, meta, actionRow }) {
    const [showAllFollowups, setShowAllFollowups] = useState(false);
    const events = Array.isArray(meta.contact_message_events) ? meta.contact_message_events : [];
    const visibleEvents = showAllFollowups ? events : events.slice(-2);
    const hiddenCount = Math.max(0, events.length - visibleEvents.length);
    const createdAt = current.created_at ? new Date(current.created_at) : null;

    return (
        <div style={{ ...sec, padding: '20px 20px 18px' }}>
            <SectionHeading
                n={1}
                label="Raw complaint (from citizen)"
                trailing={(meta.detected_language || meta.language) ? (
                    <span style={{ fontSize: 11, color: C.ink3 }}>
                        Original language: <strong style={{ color: C.ink }}>{meta.detected_language || meta.language}</strong>
                    </span>
                ) : null}
            />
            <div style={{
                position: 'relative', padding: '16px 18px 16px 40px',
                border: `1px solid ${C.hair}`, background: C.surface,
            }}>
                <span style={{
                    position: 'absolute', top: 10, left: 14, fontSize: 26, lineHeight: 1,
                    color: C.hairStrong, fontFamily: 'Georgia, serif',
                }}>&ldquo;</span>
                <div style={{
                    fontFamily: '"Source Serif 4", Georgia, serif',
                    fontSize: 16.5, lineHeight: 1.6, color: C.ink, whiteSpace: 'pre-wrap',
                }}>
                    {current.raw_message || 'No message content.'}
                </div>
            </div>
            <div style={{ marginTop: 10, fontSize: 11, color: C.ink3 }}>
                Received via WhatsApp{createdAt ? ` · ${createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })} · ${createdAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} IST` : ''}
            </div>

            {events.length > 0 && (
                <div style={{ marginTop: 18 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6, flexWrap: 'wrap', gap: 8 }}>
                        <span style={{ ...monoLbl, marginBottom: 0 }}>Citizen follow-ups · {events.length}</span>
                        {hiddenCount > 0 && !showAllFollowups && (
                            <button type="button" onClick={() => setShowAllFollowups(true)} style={{
                                background: 'none', border: 'none', color: C.green, fontSize: 11,
                                fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', padding: 0,
                            }}>
                                View full conversation ({events.length})
                            </button>
                        )}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        {visibleEvents.map((event, idx) => (
                            <div key={idx} style={{ padding: '8px 0', borderTop: idx === 0 ? 'none' : `1px solid ${C.hair}` }}>
                                <div style={{ fontSize: 10, color: C.ink3, marginBottom: 3, fontFamily: '"JetBrains Mono", monospace' }}>
                                    {event.created_at
                                        ? new Date(event.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) + ' · ' + new Date(event.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
                                        : ''}
                                </div>
                                <div style={{ fontSize: 13, color: C.ink2, lineHeight: 1.55, fontStyle: 'italic' }}>&ldquo;{event.message || '—'}&rdquo;</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {actionRow}
        </div>
    );
}

// ─── Contextual action row (Escalate/Open filing/View submission · Reply ·
// Resolve) — one location for these actions, placed with the citizen
// complaint per the spec rather than duplicated in a second sticky bar. ──
function ComplaintActionRow({ onConfirm, confirmLabel, onReply, onEscalate, escalateLabel, showEscalateHint }) {
    return (
        <div style={{ marginTop: 16, paddingTop: 14, borderTop: `1px solid ${C.hair}` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                {escalateLabel && (
                    <button onClick={onEscalate} style={{
                        padding: '9px 16px', background: C.surface, color: C.saffron, border: `1px solid ${C.saffron}`,
                        fontSize: 12, fontWeight: 700, letterSpacing: '0.04em',
                        cursor: 'pointer', fontFamily: 'inherit',
                        display: 'inline-flex', alignItems: 'center', gap: 7,
                    }}>
                        <Icon name="unlock" size={13} color={C.saffron} stroke={2} />
                        {escalateLabel}
                    </button>
                )}
                <button onClick={onReply} style={{
                    padding: '9px 16px', background: 'transparent', border: `1px solid ${C.hairStrong}`, color: C.ink,
                    fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                }}>
                    <Icon name="chat" size={12} color={C.ink} /> Reply
                </button>
                <button onClick={onConfirm} style={{
                    padding: '9px 16px', background: C.green, color: '#F5EFE0', border: 'none',
                    fontSize: 12, fontWeight: 700, letterSpacing: '0.04em',
                    cursor: 'pointer', fontFamily: 'inherit',
                    display: 'inline-flex', alignItems: 'center', gap: 7,
                }}>
                    <Icon name="check" size={13} color="#F5EFE0" stroke={2.5} />
                    {confirmLabel}
                </button>
            </div>
            {showEscalateHint && (
                <div style={{ marginTop: 8, fontSize: 11, color: C.ink3 }}>
                    Escalate to open government portal filing for this complaint.
                </div>
            )}
        </div>
    );
}

// ─── AI suggestion banner ─────────────────────────────────────
function AISuggestionBanner({ suggestion, onAccept, accepting }) {
    if (!suggestion?.ai_category) return null;
    return (
        <div style={{
            padding: '16px 20px',
            background: 'linear-gradient(120deg, #024A36 0%, #006A4D 100%)',
            color: '#F5EFE0', position: 'relative', overflow: 'hidden',
            marginBottom: 14,
        }}>
            <div style={{ position: 'absolute', right: -14, top: -14, opacity: 0.1, pointerEvents: 'none' }}>
                <Icon name="sparkle" size={110} color="#F5EFE0" stroke={1} />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
                <Icon name="sparkle" size={13} color={C.saffron} stroke={2} />
                <span style={{
                    fontFamily: '"JetBrains Mono", monospace', fontSize: 9.5,
                    letterSpacing: '0.18em', color: C.saffron, textTransform: 'uppercase', fontWeight: 700,
                }}>Sansad AI · suggested triage</span>
            </div>
            <div style={{
                fontSize: 16, fontWeight: 600, color: '#F5EFE0',
                letterSpacing: '-0.01em', lineHeight: 1.2, marginBottom: 6,
            }}>
                Categorise as{' '}
                <span style={{ textDecoration: 'underline', textDecorationStyle: 'dotted', textUnderlineOffset: 4 }}>
                    {suggestion.ai_category}{suggestion.ai_subcategory ? ` · ${suggestion.ai_subcategory}` : ''}
                </span>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                {suggestion.detected_language && (
                    <span style={{
                        fontFamily: '"JetBrains Mono", monospace', fontSize: 9.5,
                        background: 'rgba(245,239,224,0.14)', color: '#F5EFE0',
                        padding: '2px 7px', letterSpacing: '0.06em',
                    }}>language · {suggestion.detected_language}</span>
                )}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button onClick={onAccept} disabled={accepting} style={{
                    background: C.saffron, color: '#fff', border: 'none',
                    padding: '8px 16px', fontSize: 11.5, fontWeight: 700,
                    letterSpacing: '0.06em', textTransform: 'uppercase',
                    cursor: accepting ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    opacity: accepting ? 0.7 : 1,
                }}>
                    {accepting
                        ? <Loader2 size={12} className="animate-spin" />
                        : <Icon name="check" size={12} color="#fff" stroke={2.5} />}
                    Accept &amp; assign
                </button>
            </div>
        </div>
    );
}

// ─── 2 · AI understanding ─────────────────────────────────────
// Everything here is AI-generated and labelled as such. The citizen's own
// words (section 1) are always the authoritative record — this section is
// staff's aid for reading and verifying, never a replacement for it.
function AiUnderstandingSection({
    current, meta, displaySummary, followupCount, suggestedTriage, onAcceptSuggestion, accepting,
    translationState, onTranslate, geoLocation, geoAssembly, setGeoLocation, setGeoAssembly, onSaveGeo, savingGeo, geoLocked,
}) {
    const detectedLanguage = meta.detected_language || meta.language || '';
    const needsTranslation = detectedLanguage && detectedLanguage.trim().toLowerCase() !== 'english';
    const category = current.problem_domain || current.category || '';
    const subdomain = current.problem_subdomain || '';

    const rows = [
        ['Category', category ? (subdomain ? `${category} · ${subdomain}` : category) : 'Uncategorised'],
        ['Department', meta.department || '–'],
        ['Scheme', meta.scheme || '–'],
        ['Detected language', detectedLanguage || '–'],
        ['Geography confidence', meta.geography_confidence || '–'],
    ];

    const aiGeneratedBadge = (
        <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
            padding: '2px 9px', background: C.greenTint, color: C.greenInk,
        }}>AI generated</span>
    );

    return (
        <div style={sec}>
            <SectionHeading n={2} label={needsTranslation ? 'AI translation (English)' : 'AI understanding'} trailing={aiGeneratedBadge} />

            {suggestedTriage && (
                <AISuggestionBanner suggestion={suggestedTriage} onAccept={onAcceptSuggestion} accepting={accepting} />
            )}

            {needsTranslation && (
                <div style={{ marginBottom: 14, position: 'relative', border: `1px solid ${C.greenTint}`, background: C.greenWash, padding: '14px 16px 14px 38px' }}>
                    <span style={{
                        position: 'absolute', top: 8, left: 12, fontSize: 22, lineHeight: 1,
                        color: C.greenTint, fontFamily: 'Georgia, serif',
                    }}>&ldquo;</span>
                    {translationState?.translation ? (
                        <>
                            <div style={{ fontSize: 13.5, color: C.ink, lineHeight: 1.55 }}>{translationState.translation}</div>
                            <div style={{ marginTop: 8, textAlign: 'right', fontSize: 10.5, color: C.ink3 }}>
                                <Icon name="check" size={9} color={C.green} stroke={2.5} /> AI confidence: <strong style={{ color: C.greenInk }}>High</strong>
                            </div>
                        </>
                    ) : translationState?.loading ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: C.ink2 }}>
                            <Loader2 size={13} className="animate-spin" /> Translating…
                        </div>
                    ) : translationState?.error ? (
                        <div style={{ fontSize: 12, color: C.ink2 }}>
                            Translation unavailable right now.{' '}
                            <button type="button" onClick={onTranslate} style={{ background: 'none', border: 'none', color: C.green, cursor: 'pointer', fontFamily: 'inherit', fontWeight: 700, padding: 0 }}>Try again</button>
                        </div>
                    ) : (
                        <button type="button" onClick={onTranslate} style={{
                            background: 'transparent', border: `1px solid ${C.green}`, color: C.greenInk,
                            padding: '6px 12px', fontSize: 11, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase',
                            cursor: 'pointer', fontFamily: 'inherit',
                        }}>
                            Translate to English
                        </button>
                    )}
                </div>
            )}

            <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '9px 20px',
                padding: '10px 0', borderTop: `1px solid ${C.hair}`, borderBottom: `1px solid ${C.hair}`, marginBottom: 14,
            }}>
                {rows.map(([label, value]) => (
                    <div key={label} style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 9, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.08em', fontFamily: '"JetBrains Mono", monospace', marginBottom: 2 }}>{label}</div>
                        <div style={{ fontSize: 12.5, color: C.ink2, fontWeight: 500, overflowWrap: 'anywhere' }}>{value}</div>
                    </div>
                ))}
            </div>

            {displaySummary && (
                <div style={{ padding: '9px 11px', background: C.greenWash, border: `1px solid ${C.greenTint}`, marginBottom: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 5, flexWrap: 'wrap' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                            <Icon name="sparkle" size={10} color={C.green} stroke={2} />
                            <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 9, letterSpacing: '0.14em', color: C.greenInk, textTransform: 'uppercase', fontWeight: 700 }}>AI summary</span>
                        </span>
                        {followupCount > 1 && (
                            <span style={{ fontSize: 10, color: C.ink3, fontFamily: '"JetBrains Mono", monospace' }}>Based on {followupCount} citizen messages</span>
                        )}
                    </div>
                    <div style={{ fontSize: 12, color: C.ink2, lineHeight: 1.5 }}>{displaySummary}</div>
                </div>
            )}

            <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span style={{ ...monoLbl, marginBottom: 0 }}>Location · verify or correct</span>
                    {geoLocked && (
                        <span style={{
                            fontSize: 10, fontWeight: 700, padding: '2px 7px', background: C.greenWash, color: C.greenInk,
                            textTransform: 'uppercase', letterSpacing: '0.06em', display: 'inline-flex', alignItems: 'center', gap: 4,
                        }}>
                            <Icon name="check" size={9} color={C.greenInk} stroke={2.5} /> Locked
                        </span>
                    )}
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 9px', border: `1px solid ${C.hair}`, background: C.surface, flex: '1 1 150px', minWidth: 130 }}>
                        <Icon name="pin" size={10} color={C.ink3} />
                        <input value={geoLocation} onChange={(e) => setGeoLocation(e.target.value)} placeholder="Village / ward"
                            style={{ flex: 1, border: 'none', background: 'transparent', outline: 'none', fontSize: 12, color: C.ink, fontFamily: 'inherit', minWidth: 0 }} />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 9px', border: `1px solid ${C.hair}`, background: C.surface, flex: '1 1 150px', minWidth: 130 }}>
                        <input value={geoAssembly} onChange={(e) => setGeoAssembly(e.target.value)} placeholder="Assembly constituency"
                            style={{ flex: 1, border: 'none', background: 'transparent', outline: 'none', fontSize: 12, color: C.ink, fontFamily: 'inherit', minWidth: 0 }} />
                    </div>
                    <button onClick={onSaveGeo} disabled={savingGeo} style={{
                        padding: '6px 13px', background: C.ink, color: C.paper, border: 'none', flexShrink: 0,
                        fontSize: 10.5, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase',
                        cursor: savingGeo ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
                        display: 'inline-flex', alignItems: 'center', gap: 5, opacity: savingGeo ? 0.7 : 1,
                    }}>
                        {savingGeo && <Loader2 size={11} className="animate-spin" />}
                        Save
                    </button>
                </div>
            </div>
        </div>
    );
}

// ─── 3 · Attachments ──────────────────────────────────────────
function AttachmentsSection({ media, caseId }) {
    return (
        <div style={sec}>
            <span style={{ ...monoLbl, marginBottom: 12 }}>Attachments (from citizen)</span>
            {media && media.length > 0 ? (
                <BriefcaseSourceMediaViewer caseId={caseId} media={media} />
            ) : (
                <div style={{
                    border: `1px solid ${C.hair}`, background: C.surface, padding: '26px 16px',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 4,
                }}>
                    <Icon name="doc" size={18} color={C.ink3} />
                    <div style={{ fontSize: 13, fontWeight: 600, color: C.ink2, marginTop: 4 }}>No attachments</div>
                    <div style={{ fontSize: 11.5, color: C.ink3 }}>If the citizen sends images/documents, they will appear here.</div>
                </div>
            )}
        </div>
    );
}

// ─── Status actions ───────────────────────────────────────────
// Which of the 4 primary lifecycle stages a status belongs to, for the
// stepper. awaiting_location/pending_review are intake-pipeline sub-states
// of "New" — they still show up as their own quick-action links below,
// just not as a 5th/6th stepper stage.
function statusStepIndex(status) {
    const s = String(status || '').toLowerCase();
    if (s === 'in_progress') return 1;
    if (s === 'resolved' || s === 'completed') return 2;
    if (s === 'closed' || s === 'irrelevant') return 3;
    return 0;
}

function StatusStepper({ activeIndex }) {
    const steps = [
        { key: 'new', label: 'New', icon: 'doc' },
        { key: 'in_progress', label: 'In Progress', icon: 'play' },
        { key: 'resolved', label: 'Resolved', icon: 'check' },
        { key: 'closed', label: 'Closed', icon: 'check' },
    ];
    return (
        <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 16 }}>
            {steps.map((step, i) => {
                const done = i < activeIndex;
                const active = i === activeIndex;
                const fg = done ? '#fff' : active ? C.green : C.ink3;
                const circleBg = done ? C.green : C.surface;
                const circleBorder = done || active ? C.green : C.hairStrong;
                return (
                    <div key={step.key} style={{ display: 'flex', alignItems: 'flex-start', flex: i < steps.length - 1 ? 1 : '0 0 auto' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                            <div style={{
                                width: 30, height: 30, borderRadius: '50%',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                border: `2px solid ${circleBorder}`, background: circleBg,
                            }}>
                                <Icon name={done ? 'check' : step.icon} size={13} color={fg} stroke={2} />
                            </div>
                            <span style={{ fontSize: 10, fontWeight: active ? 700 : 500, color: active ? C.ink : C.ink3, whiteSpace: 'nowrap' }}>
                                {step.label}
                            </span>
                        </div>
                        {i < steps.length - 1 && (
                            <div style={{ flex: 1, height: 2, background: done ? C.green : C.hair, marginTop: 14, minWidth: 12 }} />
                        )}
                    </div>
                );
            })}
        </div>
    );
}

// The 4 primary lifecycle stages get their own quick-action buttons,
// matching the stepper above; the two intake sub-states (Needs Location,
// Needs Review) stay reachable as smaller secondary links so nothing from
// STATUS_OPTIONS becomes unreachable.
const PRIMARY_STATUS_VALUES = ['in_progress', 'resolved', 'closed', 'irrelevant'];

function StatusActions({ currentStatus, onStatusChange, updating }) {
    const primaryOptions = STATUS_OPTIONS.filter((o) => PRIMARY_STATUS_VALUES.includes(o.value));
    const secondaryOptions = STATUS_OPTIONS.filter((o) => ['awaiting_location', 'pending_review'].includes(o.value));
    return (
        <div style={asideSec}>
            <span style={monoLbl}>Update status</span>
            <StatusStepper activeIndex={statusStepIndex(currentStatus)} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 10 }}>
                {primaryOptions.map((opt) => {
                    const isCurrent = opt.value === currentStatus;
                    return (
                        <button
                            key={opt.value}
                            onClick={() => !isCurrent && onStatusChange(opt.value)}
                            disabled={!!updating || isCurrent}
                            style={{
                                padding: '8px 10px', fontSize: 11, fontWeight: 700, textAlign: 'center',
                                letterSpacing: '0.02em', cursor: (updating || isCurrent) ? 'default' : 'pointer',
                                fontFamily: 'inherit', opacity: updating && !isCurrent ? 0.7 : 1,
                                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
                                border: `1px solid ${isCurrent ? C.green : C.hair}`,
                                background: isCurrent ? C.green : C.surface,
                                color: isCurrent ? '#fff' : C.ink2,
                            }}>
                            {updating === opt.value && <Loader2 size={11} className="animate-spin" />}
                            Mark {opt.label}
                        </button>
                    );
                })}
            </div>
            {secondaryOptions.length > 0 && (
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    {secondaryOptions.map((opt) => (
                        <button key={opt.value} onClick={() => onStatusChange(opt.value)} disabled={!!updating || opt.value === currentStatus}
                            style={{
                                background: 'none', border: 'none', padding: 0, fontFamily: 'inherit',
                                fontSize: 10.5, fontWeight: 600, color: opt.value === currentStatus ? C.ink3 : C.greenInk,
                                textDecoration: opt.value === currentStatus ? 'none' : 'underline', cursor: opt.value === currentStatus ? 'default' : 'pointer',
                            }}>
                            Mark {opt.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

// ─── Activity timeline (case-level; shows the selected complaint's history) ─
function ActivityTimeline({ activities, loading }) {
    const iconFor = (action = '') => {
        if (action.includes('creat'))  return 'bolt';
        if (action.includes('translat') || action.includes('summar') || action.includes('classif')) return 'sparkle';
        if (action.includes('cluster') || action.includes('link'))  return 'cluster';
        if (action.includes('view')   || action.includes('open'))   return 'eye';
        if (action.includes('assign'))  return 'user';
        if (action.includes('notif')  || action.includes('send'))   return 'whatsapp';
        if (action.includes('complaint_added')) return 'plus';
        if (action.includes('escalat')) return 'external';
        if (action.includes('resolv') || action.includes('complet')) return 'check';
        return 'clock';
    };
    return (
        <div style={asideSec}>
            <span style={monoLbl}>Activity timeline</span>
            {loading ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0' }}>
                    <Loader2 size={16} color={C.ink3} className="animate-spin" />
                </div>
            ) : activities.length === 0 ? (
                <p style={{ fontSize: 12, color: C.ink3 }}>No activity yet.</p>
            ) : (
                <div>
                    {activities.map((act, i) => (
                        <div key={act.id || i} style={{
                            display: 'grid', gridTemplateColumns: '22px 1fr auto',
                            gap: 10, padding: '7px 0', alignItems: 'flex-start',
                            borderTop: i > 0 ? `1px solid ${C.hair}` : 'none',
                        }}>
                            <div style={{
                                width: 20, height: 20, background: C.greenWash,
                                border: `1px solid ${C.greenTint}`,
                                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                            }}>
                                <Icon name={iconFor(act.action)} size={11} color={C.green} stroke={1.8} />
                            </div>
                            <div style={{ fontSize: 12, color: C.ink, lineHeight: 1.4 }}>
                                <span style={{ fontWeight: 600 }}>{act.username || 'System'}</span>{' '}
                                <span style={{ color: C.ink2 }}>
                                    {(act.action || '').replace(/_/g, ' ')}
                                    {act.new_value ? ` → ${act.new_value}` : ''}
                                </span>
                            </div>
                            <div style={{
                                fontFamily: '"JetBrains Mono", monospace',
                                fontSize: 10, color: C.ink3, whiteSpace: 'nowrap',
                            }}>
                                {act.created_at
                                    ? new Date(act.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
                                    : ''}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ─── Government status label/helpers (used across the tab strip, the
// filing section, and the resolved-complaint summary) ─────────────
const GOVT_STATUS_LABEL = {
    not_forwarded: 'Not forwarded',
    pending_staff_submit: 'Ready to file — staff action needed',
    submitted: 'Submitted to portal',
    under_review: 'Under review',
    escalated: 'Escalated',
    resolved: 'Resolved by department',
    rejected: 'Rejected by department',
};

function isGovtAlreadyFiled(item) {
    if (!item) return false;
    if (String(item.govt_reference_number || '').trim()) return true;
    return ['submitted', 'under_review', 'escalated', 'resolved', 'rejected'].includes(
        String(item.govt_status || '').toLowerCase(),
    );
}

function GovtSyncCopyField({ label, value }) {
    const toast = useToast();
    if (!value) return null;
    return (
        <div style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ fontSize: 9.5, fontFamily: '"JetBrains Mono", monospace', color: C.ink3, letterSpacing: '0.1em', textTransform: 'uppercase' }}>{label}</span>
                <button
                    type="button"
                    onClick={() => { navigator.clipboard?.writeText(value); toast.success(`${label} copied`); }}
                    style={{ fontSize: 10, color: C.green, background: 'none', border: 'none', cursor: 'pointer', fontFamily: '"JetBrains Mono", monospace' }}
                >
                    copy
                </button>
            </div>
            <div style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.5, background: C.surface, border: `1px solid ${C.hair}`, padding: '8px 10px', whiteSpace: 'pre-wrap' }}>
                {value}
            </div>
        </div>
    );
}

function formatGovtPortalDetailRows(statusCheck) {
    const detail = statusCheck?.portal_detail || {};
    const rows = [
        ['Portal status', detail.status_text || statusCheck?.raw_portal_status],
        ['Sub-status', detail.sub_status_text],
        ['District', detail.district],
        ['Department', detail.department_name || detail.department],
        ['Category', detail.category],
        ['Office', detail.office],
        ['Officer', detail.officer],
        ['Office contact', detail.office_contact],
        ['Office email', detail.office_email],
        ['Current position', detail.pendency_details],
        ['Subject', detail.subject],
        ['Filed on portal', detail.grievance_date],
        ['Last action', detail.last_action_date],
        ['Disposed on', detail.disposed_date],
    ];
    const seen = new Set();
    return rows.filter(([label, value]) => {
        const cleaned = String(value || '').trim();
        if (!cleaned) return false;
        const key = `${label}:${cleaned}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    }).map(([label, value]) => [label, String(value).trim()]);
}

function formatGovtCheckedAt(value) {
    if (!value) return '';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function GovernmentJourneyPanel({ current }) {
    const govtStatus = String(current.govt_status || 'not_forwarded').toLowerCase();
    const alreadyFiled = isGovtAlreadyFiled(current);
    const submitted = alreadyFiled || govtStatus === 'pending_staff_submit';
    const activeIndex = alreadyFiled
        ? (['resolved', 'rejected'].includes(govtStatus) ? 4 : ['under_review', 'escalated'].includes(govtStatus) ? 3 : 2)
        : (submitted ? 1 : 0);
    const filedDate = formatShortDate(current.govt_status_updated_at || current.updated_at || current.created_at);
    const steps = [
        { label: 'Filed', date: filedDate || '22 Aug' },
        { label: 'Registered', date: filedDate || '22 Aug' },
        { label: 'Sent for scrutiny', date: activeIndex >= 2 ? filedDate || '24 Aug' : 'Pending' },
        { label: 'Department action', date: ['resolved', 'rejected'].includes(govtStatus) ? filedDate || 'Pending' : 'Pending' },
    ];
    const portalName = current.portal_name || current.govt_portal_name || 'Government portal';
    const ref = current.govt_reference_number ? `#${current.govt_reference_number}` : 'Not filed yet';
    const owner = current.latest_status_check?.portal_detail?.officer || current.latest_status_check?.portal_detail?.office || current.govt_department || 'Awaiting department update';

    return (
        <div style={{ padding: '0 76px 54px', background: C.paper }}>
            <div style={{
                border: `1px solid ${C.hair}`,
                borderRadius: 23,
                background: '#FFFDF7',
                padding: '58px 62px 60px',
                minHeight: 382,
                overflow: 'hidden',
            }}>
                <div style={{ marginBottom: 62 }}>
                    <div style={{
                        fontFamily: '"JetBrains Mono", monospace', color: C.ink3,
                        textTransform: 'uppercase', letterSpacing: '0.14em', fontSize: 26, marginBottom: 16,
                        fontWeight: 800,
                    }}>
                        Government grievance journey
                    </div>
                    <div style={{ fontSize: 36, color: C.ink, fontWeight: 900, letterSpacing: '-0.045em', lineHeight: 1.08 }}>
                        Grievance {ref} · <span style={{ fontWeight: 600, color: C.ink3 }}>{portalName}</span>
                    </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(260px, 1fr))', gap: 0, overflowX: 'auto', paddingBottom: 2 }}>
                    {steps.map((step, idx) => {
                        const complete = idx < activeIndex;
                        const active = idx === activeIndex;
                        const dotBg = complete ? C.green : active ? C.saffron : '#FFFDF7';
                        const dotBorder = complete ? C.green : active ? C.saffron : C.hairStrong;
                        return (
                            <div key={step.label} style={{ minWidth: 260, paddingRight: idx === steps.length - 1 ? 0 : 38, textAlign: 'center' }}>
                                <div style={{ position: 'relative', height: 70, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
                                    {idx < steps.length - 1 && (
                                        <span style={{
                                            position: 'absolute', left: 'calc(50% + 55px)', right: 'calc(-50% + 55px)', top: 34,
                                            height: 4, background: complete ? C.green : C.hair,
                                        }} />
                                    )}
                                    <span style={{
                                        position: 'relative', zIndex: 1,
                                        width: 70, height: 70, borderRadius: '50%',
                                        background: dotBg, border: `3px solid ${dotBorder}`,
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    }}>
                                        {complete && <Icon name="check" size={36} color="#fff" stroke={3} />}
                                        {active && <span style={{ width: 22, height: 22, borderRadius: '50%', background: '#FFFDF7' }} />}
                                    </span>
                                </div>
                                <div style={{ fontSize: 28, fontWeight: 900, color: active || complete ? C.ink : C.ink3, lineHeight: 1.12, letterSpacing: '-0.04em' }}>
                                    {step.label}
                                </div>
                                <div style={{ marginTop: 22, fontSize: 24, color: C.ink3, fontFamily: '"JetBrains Mono", monospace', letterSpacing: '0.08em' }}>
                                    {step.date}
                                </div>
                            </div>
                        );
                    })}
                </div>

                <div style={{ marginTop: 58, paddingTop: 42, borderTop: `1px solid ${C.hair}`, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 86 }}>
                    <div>
                        <div style={{ fontSize: 26, color: C.ink3, fontFamily: '"JetBrains Mono", monospace', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 12 }}>
                            Department
                        </div>
                        <div style={{ fontSize: 30, color: C.ink, fontWeight: 900, lineHeight: 1.18, letterSpacing: '-0.04em', overflowWrap: 'anywhere' }}>
                            {current.govt_department || 'Not assigned yet'}
                        </div>
                    </div>
                    <div>
                        <div style={{ fontSize: 26, color: C.ink3, fontFamily: '"JetBrains Mono", monospace', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 12 }}>
                            Currently with
                        </div>
                        <div style={{ fontSize: 30, color: C.ink, fontWeight: 900, lineHeight: 1.18, letterSpacing: '-0.04em', overflowWrap: 'anywhere' }}>
                            {owner}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function govtWsUrl(path) {
    const base = API_BASE || (typeof window !== 'undefined' ? window.location.origin : '');
    const wsBase = base.replace(/^https/, 'wss').replace(/^http/, 'ws');
    const token = getAuthToken();
    return `${wsBase}${path}?token=${encodeURIComponent(token || '')}`;
}

// ─── Live, staff-controllable view of the real government portal ───
// Renders the CDP screencast frames the backend streams over the WebSocket
// and forwards mouse/keyboard back into the real page — this is the actual
// portal, with staff logging in, filling in every field, and clicking
// Submit for real. See modules/govt_sync/browser_session.py.
function GovtLiveBrowserView({ wsPath, viewport, onClose, onSessionGone, preparedFields = [], workspaceMode = false, portalName = '' }) {
    const canvasRef = useRef(null);
    const wsRef = useRef(null);
    const [connected, setConnected] = useState(false);
    const [interactionProof, setInteractionProof] = useState({ clicks: 0, keys: 0, scrolls: 0, moves: 0, last: 'No input relayed yet' });
    const vw = viewport?.width || 1280;
    const vh = viewport?.height || 900;
    // Ref so the WS effect below doesn't need this in its deps — it's a
    // fresh closure on every parent render, and we don't want to tear
    // down/reconnect the live session's WebSocket just because of that.
    const onSessionGoneRef = useRef(onSessionGone);
    onSessionGoneRef.current = onSessionGone;

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return undefined;
        canvas.width = vw;
        canvas.height = vh;
        const ctx = canvas.getContext('2d');

        const ws = new WebSocket(govtWsUrl(wsPath));
        wsRef.current = ws;
        ws.onopen = () => setConnected(true);
        ws.onclose = (evt) => {
            setConnected(false);
            // 4404 = the backend's own "session not found" close code (api_router.py
            // govt_live_session_stream). Most commonly means the container that held
            // this session restarted (a deploy) since the session was opened — the
            // headless browser tab is genuinely gone, not something to keep retrying.
            if (evt?.code === 4404) onSessionGoneRef.current?.();
        };
        ws.onerror = () => setConnected(false);
        ws.onmessage = (evt) => {
            let msg;
            try { msg = JSON.parse(evt.data); } catch { return; }
            if (msg.type === 'frame' && msg.data) {
                const img = new Image();
                img.onload = () => ctx.drawImage(img, 0, 0, vw, vh);
                img.src = `data:image/jpeg;base64,${msg.data}`;
            }
        };

        return () => {
            try { ws.close(); } catch { /* noop */ }
            wsRef.current = null;
        };
    }, [wsPath, vw, vh]);

    function sendInput(ev) {
        const ws = wsRef.current;
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'input', event: ev }));
            setInteractionProof((prev) => {
                const next = { ...prev };
                if (ev.type === 'mousedown') {
                    next.clicks += 1;
                    next.last = `Click relayed at ${ev.x}, ${ev.y}`;
                } else if (ev.type === 'keydown') {
                    next.keys += 1;
                    next.last = ev.printable ? 'Typed character relayed' : `Key relayed: ${ev.key || 'unknown'}`;
                } else if (ev.type === 'wheel') {
                    next.scrolls += 1;
                    next.last = `Scroll relayed (${Math.round(ev.deltaY || 0)}px)`;
                } else if (ev.type === 'mousemove') {
                    next.moves += 1;
                    if (next.moves % 15 === 0) next.last = `Mouse movement relayed at ${ev.x}, ${ev.y}`;
                }
                return next;
            });
        }
    }

    function scaled(e) {
        const rect = canvasRef.current.getBoundingClientRect();
        return {
            x: Math.round(((e.clientX - rect.left) / rect.width) * vw),
            y: Math.round(((e.clientY - rect.top) / rect.height) * vh),
        };
    }

    const canvas = (
        <>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 11, color: connected ? C.greenInk : C.saffron, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: connected ? C.green : C.saffron, display: 'inline-block' }} />
                    {connected ? 'Live — staff input is relayed into the real portal session' : 'Connecting to live portal session…'}
                </span>
                {onClose && (
                    <button type="button" onClick={onClose} style={{ fontSize: 10.5, color: C.ink3, background: 'none', border: 'none', cursor: 'pointer' }}>
                        Close session
                    </button>
                )}
            </div>
            <canvas
                ref={canvasRef}
                tabIndex={0}
                style={{ width: '100%', aspectRatio: `${vw} / ${vh}`, border: `1px solid ${C.hair}`, outline: 'none', cursor: 'default', background: '#fff' }}
                onClick={(e) => { e.currentTarget.focus(); sendInput({ type: 'mousedown', ...scaled(e) }); sendInput({ type: 'mouseup', ...scaled(e) }); }}
                onMouseMove={(e) => sendInput({ type: 'mousemove', ...scaled(e) })}
                onMouseDown={(e) => sendInput({ type: 'mousedown', ...scaled(e) })}
                onMouseUp={(e) => sendInput({ type: 'mouseup', ...scaled(e) })}
                onWheel={(e) => { e.preventDefault(); sendInput({ type: 'wheel', deltaX: e.deltaX, deltaY: e.deltaY }); }}
                onKeyDown={(e) => {
                    e.preventDefault();
                    const printable = e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey;
                    sendInput({ type: 'keydown', key: e.key, printable });
                }}
            />
        </>
    );

    if (workspaceMode) {
        return (
            <div style={{ marginTop: 8, marginBottom: 10, border: `1px solid ${C.hairStrong}`, background: C.surface }}>
                <div style={{
                    padding: '12px 14px', borderBottom: `1px solid ${C.hair}`, background: C.paperDeep,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap',
                }}>
                    <div>
                        <div style={{ ...monoLbl, marginBottom: 4 }}>LOCAL/MOCK TEST · Experimental spike</div>
                        <div style={{ fontSize: 17, fontWeight: 700, color: C.ink }}>Government Filing Workspace</div>
                        <div style={{ fontSize: 12, color: C.ink2, marginTop: 3 }}>
                            {portalName || 'Government portal'} · real browser stream, no guessed autofill
                        </div>
                    </div>
                    <div style={{ fontSize: 11, color: C.greenInk, background: C.greenWash, border: `1px solid ${C.green}`, padding: '7px 10px', fontWeight: 700 }}>
                        Needle prepares → Human reviews → Portal submits
                    </div>
                </div>
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'minmax(0, 1.65fr) minmax(250px, 0.85fr)',
                    gap: 12,
                    padding: 12,
                }}>
                    <div style={{ minWidth: 0 }}>
                        <div style={{ ...monoLbl, marginBottom: 6 }}>Live government browser/session view</div>
                        {canvas}
                        <div style={{
                            marginTop: 8, display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0,1fr))',
                            border: `1px solid ${C.hair}`, background: C.paper, fontSize: 11, color: C.ink2,
                        }}>
                            {[
                                ['Clicks', interactionProof.clicks],
                                ['Keys', interactionProof.keys],
                                ['Scrolls', interactionProof.scrolls],
                                ['Moves', interactionProof.moves],
                            ].map(([label, value]) => (
                                <div key={label} style={{ padding: '7px 8px', borderRight: label === 'Moves' ? 'none' : `1px solid ${C.hair}` }}>
                                    <div style={{ fontSize: 9, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</div>
                                    <strong style={{ color: C.ink }}>{value}</strong>
                                </div>
                            ))}
                        </div>
                        <div style={{ marginTop: 6, fontSize: 11, color: C.ink3 }}>
                            Interaction proof: {interactionProof.last}
                        </div>
                    </div>
                    <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <div style={{ border: `1px solid ${C.hair}`, background: C.paper, padding: 10 }}>
                            <div style={{ ...monoLbl, marginBottom: 7 }}>Current step</div>
                            <div style={{ fontSize: 13, color: C.ink, fontWeight: 700 }}>{connected ? 'Government login / filing form' : 'Starting government session'}</div>
                            <div style={{ fontSize: 11.5, color: C.ink3, lineHeight: 1.5, marginTop: 5 }}>
                                Staff completes login, CAPTCHA, OTP, navigation, field entry, review, and final submit manually inside this live session.
                            </div>
                        </div>
                        <div style={{ border: `1px solid ${C.hair}`, background: C.paper, padding: 10 }}>
                            <div style={{ ...monoLbl, marginBottom: 7 }}>Prepared Fields / Copy Source</div>
                            {preparedFields.length ? preparedFields.map(([label, value]) => (
                                <div key={label} style={{ marginBottom: 8 }}>
                                    <div style={{ fontSize: 9.5, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 3 }}>{label}</div>
                                    <div style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.45, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{value}</div>
                                </div>
                            )) : (
                                <div style={{ fontSize: 12, color: C.ink3 }}>No prepared fields available yet.</div>
                            )}
                        </div>
                        <div style={{ border: `1px solid ${C.saffron}`, background: C.saffronTint, padding: 10, fontSize: 11.5, color: C.ink2, lineHeight: 1.5 }}>
                            <strong style={{ color: C.saffron }}>Final-submit protection:</strong> Needle does not click Submit. Stop before any real government submission during this spike.
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div style={{ marginTop: 8, marginBottom: 10 }}>
            {canvas}
        </div>
    );
}

// ─── 4 · Government portal filing ─────────────────────────────
// Staff-assisted forwarding to a state grievance portal (Rajasthan Sampark,
// UP Jansunwai, CPGRAMS). "Open live portal" launches a real browser session
// on the backend and streams it here — staff log in, the session auto-
// navigates to the grievance form once a portal's post-login path is
// configured, and staff read the AI worksheet below and type everything
// into the real page themselves (no field is auto-filled — see
// modules/govt_sync/browser_session.py's module docstring for why).
//
// LOCKED until this complaint is escalated — filing is a deliberate staff
// decision made after reviewing the citizen's complaint, not something that
// happens automatically the moment a case is opened.
const GovtSyncSection = forwardRef(function GovtSyncSection({ caseId, isMp, onSubmitted, onGovtStateChange }, ref) {
    const toast = useToast();
    // The portal a tenant can use is derived server-side from tenant -> constituency
    // -> state (tenant_profiles.state) — never a staff choice. This is a read-only
    // preview of that resolution, not a picker; the backend re-resolves it on every
    // translate/session-start call regardless of anything sent from here.
    const [resolvedPortal, setResolvedPortal] = useState(null); // /api/govt-portal response
    const [govtState, setGovtState] = useState(null); // /api/cases/{id}/govt response
    const [worksheet, setWorksheet] = useState(null);  // response from /govt/translate (includes portal_contact_number, staff_action_note)
    const [refInput, setRefInput] = useState('');
    const [busy, setBusy] = useState(false);
    const [needsGovtVerification, setNeedsGovtVerification] = useState(false); // set when /govt/poll reports the OTP-gated portal session needs re-verification (Settings → Government Portal)
    // Interactive status-check flow (a live human-verification sequence solved
    // per lookup, not a persisted OTP session — Karnataka is one CAPTCHA step,
    // Maharashtra is CAPTCHA -> OTP+CAPTCHA -> CAPTCHA). null when no attempt
    // is in progress; otherwise { attempt_id, pending: [{kind, challenge}, ...] }
    // — pending is whatever the backend most recently said is needed next.
    const [interactiveAttempt, setInteractiveAttempt] = useState(null);
    const [interactiveAnswers, setInteractiveAnswers] = useState({ captcha: '', otp: '' });
    const [liveSession, setLiveSession] = useState(null); // { session_id, ws_path, viewport, portal_name }
    const [liveConnecting, setLiveConnecting] = useState(false);
    const liveSessionRef = useRef(null); // mirrors liveSession so the unmount cleanup below sees the latest value, not a stale closure
    const [hostedSessions, setHostedSessions] = useState([]);
    const [hostedMeta, setHostedMeta] = useState({ global_count: 0, max_concurrent: 3 });
    const portalFetchRef = useRef(null); // the /api/govt-portal promise — awaited by Escalate so it never guesses at a value still in flight

    useEffect(() => {
        if (!caseId) return;
        setNeedsGovtVerification(false);
        setInteractiveAttempt(null);
        setInteractiveAnswers({ captcha: '', otp: '' });
        apiGet(`/api/cases/${caseId}/govt`).then(setGovtState).catch(() => setGovtState(null));
    }, [caseId]);

    useEffect(() => {
        // Closing the modal/switching cases shouldn't leave a live browser session open.
        return () => {
            const session = liveSessionRef.current;
            if (session) {
                apiPost(`/api/cases/${caseId}/govt/session/${session.session_id}/close`, {}).catch(() => {});
            }
        };
    }, [caseId]);

    useEffect(() => {
        portalFetchRef.current = apiGet('/api/govt-portal')
            .then((data) => { setResolvedPortal(data); return data; })
            .catch(() => { setResolvedPortal(null); return null; });
    }, []);

    function loadHostedSessions() {
        return apiGet('/api/govt/sessions')
            .then((data) => {
                setHostedSessions(data.sessions || []);
                setHostedMeta({
                    global_count: data.global_count || 0,
                    max_concurrent: data.max_concurrent || 3,
                });
                return data;
            })
            .catch(() => null);
    }

    useEffect(() => {
        loadHostedSessions();
        const timer = setInterval(loadHostedSessions, 15000);
        return () => clearInterval(timer);
    }, []);

    useEffect(() => {
        onGovtStateChange?.(caseId, govtState?.case || null);
    }, [caseId, govtState, onGovtStateChange]);

    // Whether this tenant's config actually turns on live browser automation
    // (only meaningful once /api/govt-portal has answered — see
    // resolveEscalateMode below, which is what callers should use).
    const liveAutomationEnabled = resolvedPortal?.live_automation_enabled === true;
    // False once we've confirmed this specific portal can't be reached from a
    // live session (e.g. Maharashtra — a network-level block on our EC2 IP,
    // 2026-08-19: see PROJECT_MEMORY.md). Independent of the global automation
    // switch above; a portal-level fact, not an ops toggle.
    const portalSupportsLiveSession = resolvedPortal?.portal?.live_session_supported !== false;
    // True only for portals whose status check needs a live, staff-present,
    // per-lookup CAPTCHA/OTP (currently Karnataka iPGRS) — distinct from
    // Rajasthan's needsGovtVerification (a persisted session going stale).
    const interactiveStatusCheck = resolvedPortal?.portal?.interactive_status_check === true;

    // Awaits the real /api/govt-portal answer instead of guessing at one still
    // in flight (a fast click could otherwise race ahead of the fetch). Three
    // outcomes:
    //  'live'            — open a live browser session inside Needle, as usual.
    //  'manual_redirect' — this portal can't do live sessions at all. Escalate
    //                      opens the real portal in a NEW BROWSER TAB (the
    //                      staff's own network, not EC2's, so it isn't subject
    //                      to whatever's blocking our infrastructure) and shows
    //                      the AI worksheet in Needle to copy from.
    //  'manual_worksheet'— global automation is off. Worksheet only, same as
    //                      before; staff navigates to the portal themselves.
    async function resolveEscalateMode() {
        const data = resolvedPortal != null ? resolvedPortal : await portalFetchRef.current;
        if (data?.portal?.live_session_supported === false) return 'manual_redirect';
        return data?.live_automation_enabled === true ? 'live' : 'manual_worksheet';
    }

    // window.open must happen as close to synchronously-within-the-click as
    // possible or Safari/Chrome treat it as an unrequested popup and block it —
    // this is why resolveEscalateMode() is awaited first (usually resolves
    // instantly, since /api/govt-portal is fetched on mount) rather than after
    // handlePrepare()'s network round trip.
    async function handleEscalateManualRedirect() {
        const data = resolvedPortal != null ? resolvedPortal : await portalFetchRef.current;
        const entryUrl = data?.portal?.entry_url || data?.portal?.base_url;
        if (entryUrl) {
            window.open(entryUrl, '_blank', 'noopener,noreferrer');
            toast.success(`Opening ${data?.portal?.portal_name || 'the government portal'} in a new tab — worksheet is ready below to copy from`);
        } else {
            toast.error('Could not open the portal — no URL on file. Preparing the worksheet anyway.');
        }
        return handlePrepare();
    }

    // Exposed so Escalate (in the citizen complaint's action row) can trigger
    // this section's filing flow. Rebind when caseId/govtState change so a
    // thread switch opens the right case.
    useImperativeHandle(
        ref,
        () => ({
            openLiveSession: async () => {
                const mode = await resolveEscalateMode();
                if (mode === 'live') return handleOpenLive();
                if (mode === 'manual_redirect') return handleEscalateManualRedirect();
                return handlePrepare();
            },
        }),
        [caseId, govtState, resolvedPortal],
    );

    if (!caseId) return null;
    const status = govtState?.case?.govt_status || 'not_forwarded';
    const hasPortal = !!govtState?.case?.govt_portal_id;
    const alreadyFiled = isGovtAlreadyFiled(govtState?.case);
    const supported = resolvedPortal?.supported ?? true; // don't flash "unsupported" before the first fetch resolves
    const locked = !hasPortal && !alreadyFiled;

    function setLive(session) {
        liveSessionRef.current = session;
        setLiveSession(session);
    }

    // The backend's live sessions live in one process's memory (see
    // modules/govt_sync/browser_session.py) — they don't survive that
    // process restarting, which happens on every backend deploy. If staff
    // had a session open across one, the browser tab is genuinely gone;
    // the fix is opening a new session, not retrying the old one. Clear
    // local state and say so plainly instead of leaving stale buttons that
    // 404 every time they're pressed.
    function handleSessionGone() {
        setLive(null);
        toast.error('That live session ended (the server restarted since it was opened) — click Escalate on the complaint to start a new one');
    }

    async function handleOpenLive() {
        const storedRef = String(govtState?.case?.govt_reference_number || '').trim();
        if (isGovtAlreadyFiled(govtState?.case)) {
            toast.error(storedRef
                ? `This case is already filed on the government portal (reference ${storedRef}).`
                : 'This case is already filed on the government portal.');
            return;
        }
        setLiveConnecting(true);
        try {
            const listed = await loadHostedSessions();
            const existing = (listed?.sessions || []).find((item) => item.case_id === caseId);
            if (existing) {
                setLive(existing);
                toast.success('Reconnected to the open portal session');
                return;
            }
            toast.info('Opening the government portal…');
            const result = await apiPost(`/api/cases/${caseId}/govt/session/start`, {});
            setLive(result);
            toast.success('Live portal session open — log in to continue');
            const refreshed = await apiGet(`/api/cases/${caseId}/govt`);
            setGovtState(refreshed);
            await loadHostedSessions();
        } catch (e) {
            setLive(null);
            await loadHostedSessions();
            toast.error(e.message || 'Could not open a live session');
        } finally {
            setLiveConnecting(false);
        }
    }

    async function handleCloseLive() {
        const session = liveSessionRef.current;
        if (!session) return;
        try {
            await apiPost(`/api/govt/sessions/${session.session_id}/close`, {});
        } catch { /* best effort */ }
        setLive(null);
        await loadHostedSessions();
    }

    async function handleEndHostedSession(sessionId) {
        setBusy(true);
        try {
            await apiPost(`/api/govt/sessions/${sessionId}/close`, {});
            if (liveSessionRef.current?.session_id === sessionId) setLive(null);
            toast.success('Live portal session ended');
            await loadHostedSessions();
        } catch (e) {
            toast.error(e.message || 'Could not end that session');
        } finally {
            setBusy(false);
        }
    }

    async function handleEndAllHostedSessions() {
        setBusy(true);
        try {
            const result = await apiPost('/api/govt/sessions/close-all', {});
            setLive(null);
            toast.success(result.closed ? `Ended ${result.closed} live portal session${result.closed === 1 ? '' : 's'}` : 'No live sessions were open');
            await loadHostedSessions();
        } catch (e) {
            toast.error(e.message || 'Could not end live sessions');
        } finally {
            setBusy(false);
        }
    }

    async function handleCaptureReference() {
        const session = liveSessionRef.current;
        if (!session) return;
        setBusy(true);
        try {
            const result = await apiPost(`/api/cases/${caseId}/govt/session/${session.session_id}/capture-reference`, {});
            if (result.reference_number) {
                setRefInput(result.reference_number);
                toast.success('Reference number found — confirm and save below');
            } else {
                toast.error('Could not read a reference number automatically — copy it from the view and paste it below');
            }
        } catch (e) {
            if (e.message === 'Live session not found') { handleSessionGone(); return; }
            toast.error(e.message || 'Capture failed');
        } finally {
            setBusy(false);
        }
    }

    async function handlePrepare() {
        setBusy(true);
        toast.info('Preparing the filing worksheet…');
        try {
            const result = await apiPost(`/api/cases/${caseId}/govt/translate`, {});
            setWorksheet(result);
            const refreshed = await apiGet(`/api/cases/${caseId}/govt`);
            setGovtState(refreshed);
            toast.success(`Worksheet ready for ${result.portal.portal_name}`);
        } catch (e) {
            toast.error(e.message || 'AI translation failed — try again');
        } finally {
            setBusy(false);
        }
    }

    async function handleSubmitRef() {
        if (!refInput.trim()) { toast.error('Enter the reference number the portal gave you'); return; }
        setBusy(true);
        try {
            const result = await apiPost(`/api/cases/${caseId}/govt/submit`, { reference_number: refInput.trim() });
            const refreshed = await apiGet(`/api/cases/${caseId}/govt`);
            setGovtState(refreshed);
            setRefInput('');
            if (liveSessionRef.current) {
                await handleCloseLive();
            }
            onSubmitted?.(caseId, result.status || 'in_progress');
            toast.success('Marked as submitted to the portal');
        } catch (e) {
            toast.error(e.message || 'Could not save reference number');
        } finally {
            setBusy(false);
        }
    }

    async function handlePollNow() {
        setBusy(true);
        try {
            const result = await apiPost(`/api/cases/${caseId}/govt/poll`, {});
            const refreshed = await apiGet(`/api/cases/${caseId}/govt`);
            setGovtState(refreshed);
            setNeedsGovtVerification(!!result.needs_verification);
            if (result.needs_verification) {
                toast.warning(result.note || 'Verify Rajasthan Sampark access under Settings → Government Portal, then try again.');
            } else {
                const raw = String(result.raw_portal_status || '').trim();
                toast.success(result.changed ? `Status updated: ${GOVT_STATUS_LABEL[result.govt_status] || result.govt_status}` : (raw ? `Portal still says: ${raw}` : (result.note || 'No change yet')));
            }
        } catch (e) {
            toast.error(e.message || 'Status check failed');
        } finally {
            setBusy(false);
        }
    }

    // Interactive status-check flow — a live human-verification sequence
    // solved fresh per lookup, distinct from handlePollNow's single
    // synchronous call. Karnataka is a single CAPTCHA round trip; Maharashtra
    // is CAPTCHA -> OTP+CAPTCHA -> CAPTCHA (see govt_sync/adapters/
    // maharashtra_aaplesarkar.py). interactiveAttempt.pending is whatever
    // pending_human_verification the backend just returned — the UI renders
    // whatever kinds are present each time, rather than assuming a single
    // CAPTCHA step; this is what lets the SAME two handlers below drive
    // either portal without a portal-specific branch here.
    async function handleStartInteractiveCheck() {
        setBusy(true);
        try {
            const result = await apiPost(`/api/cases/${caseId}/govt/status-check/start`, {});
            setInteractiveAttempt({ attempt_id: result.attempt_id, pending: result.pending_human_verification || [] });
            setInteractiveAnswers({ captcha: '', otp: '' });
        } catch (e) {
            toast.error(e.message || 'Could not start status check');
        } finally {
            setBusy(false);
        }
    }

    async function handleAdvanceInteractiveCheck() {
        if (!interactiveAttempt) return;
        const kinds = new Set((interactiveAttempt.pending || []).map(r => r.kind));
        const body = { captcha: interactiveAnswers.captcha.trim() };
        if (kinds.has('otp')) body.otp = interactiveAnswers.otp.trim();
        if (!body.captcha || (kinds.has('otp') && !body.otp)) return;

        setBusy(true);
        try {
            const result = await apiPost(
                `/api/cases/${caseId}/govt/status-check/${interactiveAttempt.attempt_id}/advance`,
                body,
            );
            if (result.state === 'failed') {
                toast.error(result.note || 'Verification failed — try again');
                setInteractiveAttempt(null);
                setInteractiveAnswers({ captcha: '', otp: '' });
                return;
            }
            if (result.state === 'complete') {
                const refreshed = await apiGet(`/api/cases/${caseId}/govt`);
                setGovtState(refreshed);
                setInteractiveAttempt(null);
                setInteractiveAnswers({ captcha: '', otp: '' });
                const raw = String(result.raw_portal_status || '').trim();
                toast.success(result.changed ? `Status updated: ${GOVT_STATUS_LABEL[result.govt_status] || result.govt_status}` : (raw ? `Portal still says: ${raw}` : (result.note || 'No change yet')));
                return;
            }
            // Still awaiting input — a later stage of a multi-stage flow
            // (Maharashtra). Same attempt_id, new set of requirements.
            setInteractiveAttempt({ attempt_id: interactiveAttempt.attempt_id, pending: result.pending_human_verification || [] });
            setInteractiveAnswers({ captcha: '', otp: '' });
        } catch (e) {
            toast.error(e.message || 'Could not verify — try again');
        } finally {
            setBusy(false);
        }
    }

    async function handleNotifyCitizen() {
        setBusy(true);
        try {
            await apiPost(`/api/cases/${caseId}/govt/notify-citizen`, {});
            toast.success('WhatsApp update sent to citizen');
        } catch (e) {
            toast.error(e.message || 'Failed to notify citizen');
        } finally {
            setBusy(false);
        }
    }

    const ws = worksheet?.worksheet || govtState?.case?.govt_submission_worksheet;
    const preparedFields = [
        ['Department', ws?.department],
        ['Subject', ws?.subject],
        ['Description', ws?.description],
        ['Priority category', ws?.priority_category],
        ['Filer/citizen name to enter on portal', worksheet?.portal_filer_name || liveSession?.portal_filer_name],
        ['Contact number to enter on portal', worksheet?.portal_contact_number || liveSession?.portal_contact_number],
    ].filter(([, value]) => String(value || '').trim()).map(([label, value]) => [label, String(value).trim()]);
    // A case keeps whatever portal it was prepared against forever, even after a
    // better match becomes available (e.g. this tenant's state didn't have its own
    // portal yet when this case was first prepared, so it fell back to CPGRAMS —
    // then the real state portal got added later). Only worth flagging/fixing while
    // nothing has actually been filed with the government yet — once status moves
    // past pending_staff_submit, a real submission already happened somewhere and
    // silently reassigning the portal after the fact would misrepresent that.
    const portalMismatch = (
        hasPortal && status === 'pending_staff_submit' &&
        resolvedPortal?.portal && resolvedPortal.portal.id !== govtState.case.govt_portal_id
    );

    return (
        <div style={sec}>
            <SectionHeading
                n={3}
                label="Government portal filing"
                trailing={
                    <span style={{
                        fontSize: 10, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase',
                        padding: '3px 10px', display: 'inline-flex', alignItems: 'center', gap: 5,
                        background: C.surface,
                        border: `1px solid ${locked ? C.saffron : (status === 'resolved' ? C.green : status === 'rejected' ? C.red : C.saffron)}`,
                        color: locked ? C.saffron : (status === 'resolved' ? C.greenInk : status === 'rejected' ? C.red : C.saffron),
                    }}>
                        <Icon name={locked ? 'lock' : 'unlock'} size={10} stroke={2.2} />
                        {locked ? 'Locked' : (GOVT_STATUS_LABEL[status] || status)}
                    </span>
                }
            />

            {locked ? (
                <div style={{
                    border: `1px dashed ${C.saffron}`, background: C.surface, padding: '22px 20px',
                    display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center', textAlign: 'center',
                }}>
                    <div style={{
                        width: 32, height: 32, borderRadius: '50%', background: C.saffronTint,
                        border: `1px solid ${C.saffron}`, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <Icon name="lock" size={14} color={C.saffron} stroke={2} />
                    </div>
                    <div style={{ fontSize: 13, color: C.ink2, lineHeight: 1.5, maxWidth: 420 }}>
                        This section will be available after staff escalates this complaint.
                    </div>
                    <button
                        type="button"
                        onClick={async () => {
                            const mode = await resolveEscalateMode();
                            if (mode === 'live') return handleOpenLive();
                            if (mode === 'manual_redirect') return handleEscalateManualRedirect();
                            return handlePrepare();
                        }}
                        style={{
                            marginTop: 4, padding: '9px 18px', background: C.surface, color: C.saffron,
                            border: `1px solid ${C.saffron}`, fontSize: 12, fontWeight: 700, letterSpacing: '0.04em',
                            cursor: 'pointer', fontFamily: 'inherit',
                            display: 'inline-flex', alignItems: 'center', gap: 7,
                        }}
                    >
                        <Icon name="lock" size={12} color={C.saffron} stroke={2.2} /> Escalate to proceed
                    </button>
                    {resolvedPortal?.portal && supported && (
                        <div style={{ fontSize: 11, color: C.ink3, marginTop: 2 }}>
                            Will file via <strong style={{ color: C.ink2 }}>{resolvedPortal.portal.portal_name}</strong>
                            {resolvedPortal.state ? ` (${resolvedPortal.state})` : ''} once escalated.
                            {!portalSupportsLiveSession && ' This portal can\'t be reached from a live session right now — Escalate will open it in a new tab and prepare the AI worksheet here to copy from.'}
                            {portalSupportsLiveSession && !liveAutomationEnabled && ' Automated filing is off for this tenant, so Escalate will prepare the AI worksheet for copy-paste filing instead of a live session.'}
                        </div>
                    )}
                    {!supported && (
                        <div style={{ fontSize: 11, color: C.ink3, fontStyle: 'italic', marginTop: 2 }}>
                            No government portal configured yet for {resolvedPortal?.state ? `state "${resolvedPortal.state}"` : "this tenant's state (none on file)"}.
                            Ask an admin to add one under Government Portals settings.
                        </div>
                    )}
                </div>
            ) : (
                <>
                    {hostedSessions.length > 0 && (
                        <div style={{
                            fontSize: 11.5, color: C.ink, background: C.saffronTint, border: `1px solid ${C.hair}`,
                            padding: '8px 10px', marginBottom: 10,
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
                                <span>
                                    Open live sessions: <strong>{hostedSessions.length}</strong>
                                    {hostedMeta.max_concurrent ? ` of ${hostedMeta.max_concurrent} on this host` : ''}
                                </span>
                                <Button size="sm" variant="outline" disabled={busy} onClick={handleEndAllHostedSessions}>
                                    End all
                                </Button>
                            </div>
                            {hostedSessions.map((item) => {
                                const minutes = Math.max(1, Math.round((item.age_seconds || 0) / 60));
                                const isThisCase = item.case_id === caseId;
                                const isViewing = liveSession?.session_id === item.session_id;
                                return (
                                    <div key={item.session_id} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 6 }}>
                                        <span style={{ flex: '1 1 160px' }}>
                                            Case #{item.case_id} · {item.portal_name || 'Portal'} · {minutes} min
                                            {isThisCase ? ' · this complaint' : ''}
                                            {isViewing ? ' · showing below' : ''}
                                        </span>
                                        {isThisCase && !isViewing && (
                                            <Button size="sm" variant="outline" disabled={liveConnecting} onClick={() => { setLive(item); toast.success('Showing the open portal session'); }}>
                                                Show
                                            </Button>
                                        )}
                                        <Button size="sm" variant="outline" disabled={busy} onClick={() => handleEndHostedSession(item.session_id)}>
                                            End
                                        </Button>
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {portalMismatch && (
                        <div style={{ fontSize: 11.5, color: C.saffron, background: C.saffronTint, padding: '8px 10px', marginBottom: 10 }}>
                            ⚠ This was prepared for <strong>{govtState?.case?.portal_name || 'a different portal'}</strong>, but
                            this tenant should now use <strong>{resolvedPortal.portal.portal_name}</strong>
                            {resolvedPortal.state ? ` (${resolvedPortal.state})` : ''} — nothing's been filed with the government
                            yet, so it's safe to fix.
                            <div style={{ marginTop: 6 }}>
                                <Button size="sm" disabled={busy} onClick={handlePrepare}>
                                    {busy ? <Loader2 size={14} className="animate-spin" /> : `Re-resolve to ${resolvedPortal.portal.portal_name}`}
                                </Button>
                            </div>
                        </div>
                    )}

                    {hasPortal && ws && (
                        <div style={{ marginTop: hasPortal && !ws ? 0 : 4 }}>
                            <GovtSyncCopyField label="Department" value={ws.department} />
                            <GovtSyncCopyField label="Subject" value={ws.subject} />
                            <GovtSyncCopyField label="Description" value={ws.description} />
                            {ws.priority_category && <GovtSyncCopyField label="Priority category" value={ws.priority_category} />}
                            {worksheet?.portal_filer_name && (
                                <GovtSyncCopyField label="Filer/citizen name to enter on portal (MP, not the constituent)" value={worksheet.portal_filer_name} />
                            )}
                            {worksheet?.portal_contact_number && (
                                <GovtSyncCopyField label="Contact number to enter on portal" value={worksheet.portal_contact_number} />
                            )}
                            {worksheet?.staff_action_note && (
                                <div style={{ fontSize: 11, color: C.ink2, marginBottom: 10, fontStyle: 'italic' }}>{worksheet.staff_action_note}</div>
                            )}
                            {!portalSupportsLiveSession && (resolvedPortal?.portal?.entry_url || resolvedPortal?.portal?.base_url) && (
                                // This portal has no live session to reopen (unlike hostedSessions
                                // above) — Escalate already opened it in a new tab once, but if
                                // staff closed that tab there's otherwise no way back in.
                                <a
                                    href={resolvedPortal.portal.entry_url || resolvedPortal.portal.base_url}
                                    target="_blank" rel="noopener noreferrer"
                                    style={{ fontSize: 11.5, color: C.green, display: 'inline-flex', alignItems: 'center', gap: 5, marginBottom: 10 }}
                                >
                                    <Icon name="external" size={12} stroke={2.2} /> Reopen {resolvedPortal.portal.portal_name}
                                </a>
                            )}
                        </div>
                    )}

                    {liveSession && (
                        <div>
                            <GovtLiveBrowserView
                                wsPath={liveSession.ws_path}
                                viewport={liveSession.viewport}
                                onClose={handleCloseLive}
                                onSessionGone={handleSessionGone}
                                preparedFields={preparedFields}
                                workspaceMode={GOVT_FILING_WORKSPACE_SPIKE}
                                portalName={liveSession.portal_name || resolvedPortal?.portal?.portal_name}
                            />
                            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                                <Button size="sm" variant="outline" disabled={busy} onClick={handleCaptureReference}>
                                    {busy ? <Loader2 size={14} className="animate-spin" /> : 'Submitted — capture reference number'}
                                </Button>
                            </div>
                        </div>
                    )}

                    {hasPortal && status === 'pending_staff_submit' && !alreadyFiled && (
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 4 }}>
                            <Input
                                placeholder="Reference number from portal"
                                value={refInput}
                                onChange={(e) => setRefInput(e.target.value)}
                                style={{ fontSize: 12.5, flex: '1 1 180px' }}
                            />
                            <Button size="sm" disabled={busy} onClick={handleSubmitRef}>
                                {busy ? <Loader2 size={14} className="animate-spin" /> : 'Mark as submitted'}
                            </Button>
                        </div>
                    )}

                    {alreadyFiled && (
                        <div style={{ marginTop: 8 }}>
                            <div style={{ fontSize: 11.5, color: C.ink2, marginBottom: 8 }}>
                                Ref: <strong style={{ color: C.ink }}>{govtState?.case?.govt_reference_number || '—'}</strong>
                                {govtState?.case?.govt_status_updated_at && (
                                    <> · updated {new Date(govtState.case.govt_status_updated_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</>
                                )}
                            </div>
                            {formatGovtPortalDetailRows(govtState?.latest_status_check).length > 0 && (
                                <div style={{ fontSize: 11.5, color: C.ink2, background: C.surface, border: `1px solid ${C.hair}`, padding: '10px', marginBottom: 8 }}>
                                    <div style={{ fontSize: 9.5, fontFamily: '"JetBrains Mono", monospace', color: C.ink3, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6 }}>
                                        Current portal position
                                        {formatGovtCheckedAt(govtState?.latest_status_check?.checked_at) ? ` · checked ${formatGovtCheckedAt(govtState.latest_status_check.checked_at)}` : ''}
                                    </div>
                                    <div style={{ display: 'grid', gap: 5 }}>
                                        {formatGovtPortalDetailRows(govtState.latest_status_check).map(([label, value]) => (
                                            <div key={`${label}-${value}`} style={{ display: 'grid', gridTemplateColumns: '120px minmax(0, 1fr)', gap: 8 }}>
                                                <span style={{ color: C.ink3 }}>{label}</span>
                                                <strong style={{ color: C.ink, fontWeight: 600 }}>{value}</strong>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {needsGovtVerification && (
                                <div style={{ fontSize: 11.5, color: C.saffron, background: C.saffronTint, padding: '8px 10px', marginBottom: 8 }}>
                                    ⚠ This portal needs a fresh access verification before status can be checked again.
                                    <div style={{ marginTop: 6 }}>
                                        <a href="/dashboard/settings" style={{ color: C.saffron, textDecoration: 'underline', fontWeight: 600 }}>
                                            Verify under Settings → Government Portal
                                        </a>
                                    </div>
                                </div>
                            )}
                            {interactiveStatusCheck && interactiveAttempt && (
                                <div style={{ fontSize: 11.5, color: C.ink2, background: C.surface, border: `1px solid ${C.hair}`, padding: '10px', marginBottom: 8 }}>
                                    <div style={{ marginBottom: 6 }}>Complete the verification below to check status:</div>
                                    {(interactiveAttempt.pending || []).map((req, idx) => {
                                        if (req.kind === 'captcha') {
                                            return (
                                                <div key={idx} style={{ marginBottom: 8 }}>
                                                    {req.challenge && (
                                                        <img
                                                            src={req.challenge}
                                                            alt="CAPTCHA"
                                                            style={{ display: 'block', marginBottom: 6, border: `1px solid ${C.hair}` }}
                                                        />
                                                    )}
                                                    <Input
                                                        placeholder="CAPTCHA"
                                                        value={interactiveAnswers.captcha}
                                                        onChange={(e) => setInteractiveAnswers(a => ({ ...a, captcha: e.target.value }))}
                                                        style={{ fontSize: 12.5, maxWidth: 180 }}
                                                    />
                                                </div>
                                            );
                                        }
                                        if (req.kind === 'otp') {
                                            return (
                                                <div key={idx} style={{ marginBottom: 8 }}>
                                                    {req.challenge && (
                                                        <div style={{ fontSize: 11, color: C.ink3, marginBottom: 4 }}>{req.challenge}</div>
                                                    )}
                                                    <Input
                                                        placeholder="OTP"
                                                        value={interactiveAnswers.otp}
                                                        onChange={(e) => setInteractiveAnswers(a => ({ ...a, otp: e.target.value }))}
                                                        style={{ fontSize: 12.5, maxWidth: 180 }}
                                                    />
                                                </div>
                                            );
                                        }
                                        return null;
                                    })}
                                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                        <Button
                                            size="sm"
                                            disabled={
                                                busy || !interactiveAnswers.captcha.trim() ||
                                                ((interactiveAttempt.pending || []).some(r => r.kind === 'otp') && !interactiveAnswers.otp.trim())
                                            }
                                            onClick={handleAdvanceInteractiveCheck}
                                        >
                                            {busy ? <Loader2 size={14} className="animate-spin" /> : 'Verify'}
                                        </Button>
                                        <Button size="sm" variant="outline" disabled={busy} onClick={() => { setInteractiveAttempt(null); setInteractiveAnswers({ captcha: '', otp: '' }); }}>
                                            Cancel
                                        </Button>
                                    </div>
                                </div>
                            )}
                            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                <Button
                                    size="sm" variant="outline"
                                    disabled={busy || (interactiveStatusCheck && !!interactiveAttempt)}
                                    onClick={interactiveStatusCheck ? handleStartInteractiveCheck : handlePollNow}
                                >
                                    {busy ? <Loader2 size={14} className="animate-spin" /> : 'Check status now'}
                                </Button>
                                {isMp && (
                                    <Button size="sm" disabled={busy} onClick={handleNotifyCitizen}>
                                        <Send size={13} style={{ marginRight: 6 }} />
                                        Forward update to citizen
                                    </Button>
                                )}
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
});

// ─── Notes + response section ─────────────────────────────────
function NotesSection({ notes, setNotes, response, setResponse, draftSaved, onSave, saving, phone, isMp, onNotify, responseSectionRef, responseInputRef }) {
    return (
        <div ref={responseSectionRef} style={sec}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={monoLbl}>Internal notes</span>
                {draftSaved && (
                    <span style={{
                        fontSize: 10, color: C.saffron, fontWeight: 600,
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                    }}>
                        <span style={{ width: 5, height: 5, background: C.saffron, borderRadius: '50%' }} />
                        Draft saved locally
                    </span>
                )}
            </div>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)}
                placeholder="Add notes visible to your office staff only…"
                style={{
                    width: '100%', minHeight: 64, padding: '10px 12px',
                    border: `1px solid ${C.hair}`, background: C.surface,
                    fontFamily: 'inherit', fontSize: 12.5, color: C.ink,
                    resize: 'vertical', outline: 'none', boxSizing: 'border-box', marginBottom: 10,
                }} />

            <span style={{ ...monoLbl, marginBottom: 6 }}>Response to citizen</span>
            <textarea
                ref={responseInputRef}
                value={response}
                onChange={(e) => setResponse(e.target.value)}
                placeholder="Custom WhatsApp message (optional)…"
                style={{
                    width: '100%', minHeight: 56, padding: '10px 12px',
                    border: `1px solid ${C.hair}`, background: C.surface,
                    fontFamily: 'inherit', fontSize: 12.5, color: C.ink,
                    resize: 'vertical', outline: 'none', boxSizing: 'border-box', marginBottom: 10,
                }} />

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button onClick={onSave} disabled={saving} style={{
                    padding: '7px 14px', background: C.ink, color: C.paper, border: 'none',
                    fontSize: 11.5, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
                    cursor: saving ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
                    display: 'inline-flex', alignItems: 'center', gap: 6, opacity: saving ? 0.7 : 1,
                }}>
                    {saving && <Loader2 size={12} className="animate-spin" />}
                    Save notes
                </button>
                <button onClick={onNotify} disabled={!phone || !isMp}
                    title={!isMp ? 'Only the primary account can send notifications' : !phone ? 'No phone on file' : ''}
                    style={{
                        padding: '7px 14px', background: 'transparent',
                        border: `1px solid ${C.green}`, color: C.green,
                        fontSize: 11.5, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
                        cursor: (!phone || !isMp) ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        opacity: (!phone || !isMp) ? 0.5 : 1,
                    }}>
                    <Icon name="whatsapp" size={12} color={C.green} />
                    Send via WhatsApp
                    {!isMp && <span style={{ fontSize: 10, opacity: 0.6 }}>(Primary only)</span>}
                </button>
            </div>
        </div>
    );
}

// ─── Assign + delete ───────────────────────────────────────────
// ─── Case information (right rail) ─────────────────────────────
// Two-column reference grid (matches the reference layout) with Assignee
// folded in as a plain-looking but still-functional select, and a
// "Save geography" shortcut that saves whatever's currently in the AI
// Understanding section's location/assembly inputs — same handler, just
// surfaced here too for quick access without scrolling back up.
function CaseInformation({ current, meta, caseRef, createdAt, assignee, constituency, onAssign, staff, onDelete, userRole, onSaveGeo, savingGeo, priority, onPriorityChange }) {
    const canDelete = ['mp', 'owner', 'pr'].includes(userRole);
    const priorityValue = priority || (current.is_critical ? 'critical' : 'standard');
    const gridRows = [
        ['Priority',
            <select value={priorityValue} onChange={(e) => onPriorityChange?.(e.target.value)} style={{
                border: 'none', background: 'transparent', padding: 0,
                fontSize: 12.5, color: C.ink, fontWeight: 700, fontFamily: 'inherit', outline: 'none',
            }}>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="standard">Standard</option>
                <option value="low">Low</option>
            </select>,
         'Geography', meta.matched_value || current.location || '–'],
        ['Category', current.problem_subdomain || current.problem_domain || current.category || 'Uncategorised',
         'Location', meta.matched_value || current.location || '–'],
        ['Channel', 'WhatsApp',
         'Location · Ward', current.ward || meta.matched_value || current.location || '–'],
        ['Constituency', constituency || '–',
         'Assembly', current.assembly || meta.assembly_constituency || '–'],
    ];

    return (
        <div style={asideSec}>
            <div style={{ ...monoLbl, marginBottom: 12 }}>Case information</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 12 }}>
                {gridRows.map(([labelA, valueA, labelB, valueB], i) => (
                    <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                        <div style={{ minWidth: 0 }}>
                            <div style={{ fontSize: 9, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: '"JetBrains Mono", monospace', marginBottom: 3 }}>{labelA}</div>
                            <div style={{ fontSize: 12.5, color: C.ink, fontWeight: 600, overflowWrap: 'anywhere' }}>{valueA}</div>
                        </div>
                        <div style={{ minWidth: 0 }}>
                            <div style={{ fontSize: 9, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: '"JetBrains Mono", monospace', marginBottom: 3 }}>{labelB}</div>
                            <div style={{ fontSize: 12.5, color: C.ink, fontWeight: 600, overflowWrap: 'anywhere' }}>{valueB}</div>
                        </div>
                    </div>
                ))}
            </div>
            <div style={{ paddingTop: 10, borderTop: `1px solid ${C.hair}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                    <Icon name="user" size={12} color={C.ink3} />
                    <select value={assignee} onChange={(e) => onAssign(e.target.value)} style={{
                        border: 'none', background: 'transparent', padding: 0,
                        fontSize: 12.5, color: C.ink, fontWeight: 600, fontFamily: 'inherit', outline: 'none',
                    }}>
                        <option value="">Unassigned</option>
                        {staff.map((s) => (
                            <option key={s.username} value={s.username}>{s.display_name || s.username}</option>
                        ))}
                    </select>
                </div>
                <button onClick={onSaveGeo} disabled={savingGeo} style={{
                    padding: '6px 12px', background: C.ink, color: C.paper, border: 'none', flexShrink: 0,
                    fontSize: 10.5, fontWeight: 700, letterSpacing: '0.04em',
                    cursor: savingGeo ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
                    display: 'inline-flex', alignItems: 'center', gap: 5, opacity: savingGeo ? 0.7 : 1,
                }}>
                    {savingGeo && <Loader2 size={11} className="animate-spin" />}
                    <Icon name="doc" size={11} color={C.paper} /> Save geography
                </button>
            </div>
            {canDelete && (
                <div style={{ marginTop: 10, textAlign: 'right' }}>
                    <button onClick={onDelete} style={{
                        background: 'none', border: 'none', padding: 0, fontFamily: 'inherit',
                        fontSize: 10.5, fontWeight: 600, color: C.red, cursor: 'pointer',
                        display: 'inline-flex', alignItems: 'center', gap: 5,
                    }}>
                        <Icon name="trash" size={11} color={C.red} /> Delete case
                    </button>
                </div>
            )}
        </div>
    );
}

// ─── Resolved-complaint summary (shown in place of the 4 sections when the
// selected complaint is resolved — the tab strip and right rail stay live
// so staff can switch to another complaint or reopen this one) ────
function ResolvedComplaintSummary({ current, meta, activities, loadingActivity }) {
    const createdAt = current.created_at ? new Date(current.created_at) : null;
    const notifyAct = [...activities].reverse().find((a) => a.action === 'citizen_notified');
    const notifiedAt = notifyAct ? new Date(notifyAct.created_at) : null;

    const fields = [
        ['Category', current.problem_subdomain || current.problem_domain || current.category || 'General'],
        ['Location', meta.matched_value || current.location || '–'],
        ['Assembly', meta.assembly_constituency || current.assembly || '–'],
        ['Filed', createdAt ? createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '–'],
        ['Resolved', notifiedAt ? notifiedAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '–'],
    ];

    return (
        <>
            <div style={sec}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    {fields.map(([label, value]) => (
                        <div key={label} style={{ border: `1px solid ${C.hair}`, padding: '8px 12px', background: C.surface, minWidth: 0 }}>
                            <div style={{ fontSize: 9.5, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.08em', fontFamily: '"JetBrains Mono", monospace', marginBottom: 3 }}>{label}</div>
                            <div style={{ fontSize: 13, fontWeight: 500, color: C.ink, overflowWrap: 'anywhere' }}>{value}</div>
                        </div>
                    ))}
                </div>
            </div>
            <div style={sec}>
                <SectionHeading n={1} label="Raw complaint (from citizen)" />
                <div style={{ padding: '12px 14px', background: C.paperDeep, borderLeft: `3px solid ${C.green}`, fontSize: 13.5, lineHeight: 1.6, color: C.ink, whiteSpace: 'pre-wrap' }}>
                    {current.raw_message || 'No message content.'}
                </div>
            </div>
            {current.response_to_citizen && (
                <div style={sec}>
                    <span style={monoLbl}>Resolution message sent</span>
                    <div style={{ padding: '12px 14px', background: C.greenWash, borderLeft: `3px solid ${C.green}`, fontSize: 13, color: C.ink, lineHeight: 1.6 }}>
                        {current.response_to_citizen}
                    </div>
                </div>
            )}
            {(current.govt_status || current.govt_reference_number) && (
                <div style={sec}>
                    <SectionHeading n={3} label="Government filing" />
                    <div style={{ fontSize: 12.5, color: C.ink2 }}>
                        Status: <strong style={{ color: C.ink }}>{GOVT_STATUS_LABEL[current.govt_status] || current.govt_status || 'Not forwarded'}</strong>
                        {current.govt_reference_number && <> · Reference: <strong style={{ color: C.ink }}>{current.govt_reference_number}</strong></>}
                    </div>
                </div>
            )}
            <ActivityTimeline activities={activities} loading={loadingActivity} />
        </>
    );
}

// ─── Main export ──────────────────────────────────────────────
export default function BriefcaseCaseModal({ caseItem, color, onClose, onStatusChange, statusFilter, staff, user, onDeleteCase }) {
    const toast = useToast();
    const isMobile = useIsMobile();
    const [updating, setUpdating] = useState(null);
    const [acceptingSuggestion, setAcceptingSuggestion] = useState(false);
    const [notes, setNotes] = useState('');
    const [response, setResponse] = useState('');
    const [savingNotes, setSavingNotes] = useState(false);
    const [assignee, setAssignee] = useState('');
    const [activities, setActivities] = useState([]);
    const [loadingActivity, setLoadingActivity] = useState(false);
    const [draftSaved, setDraftSaved] = useState(false);
    const [notifyOpen, setNotifyOpen] = useState(false);
    const [notifyInput, setNotifyInput] = useState('');
    const [notifySending, setNotifySending] = useState(false);
    const [fullCase, setFullCase] = useState(null);
    const [activeCaseId, setActiveCaseId] = useState(null);
    const [geoLocation, setGeoLocation] = useState('');
    const [geoAssembly, setGeoAssembly] = useState('');
    const [savingGeo, setSavingGeo] = useState(false);
    const [followBusy, setFollowBusy] = useState(false);
    const [translations, setTranslations] = useState({}); // { [caseId]: { loading, translation, error, alreadyEnglish } }
    const responseSectionRef = useRef(null);
    const responseInputRef = useRef(null);
    const govtSyncRef = useRef(null);      // imperative handle into GovtSyncSection — lets Escalate trigger its live-session flow
    const govtSectionRef = useRef(null);   // scroll target so Escalate brings that section into view
    const aiSectionRef = useRef(null);     // scroll target for "View AI summary" in the needs-review banner

    useEffect(() => {
        if (!caseItem) return;
        setFullCase(caseItem);
        setActiveCaseId(caseItem.id);
        apiGet(`/api/cases/${caseItem.id}`)
            .then((result) => {
                setFullCase({ ...caseItem, ...result });
            })
            .catch(() => setFullCase(caseItem));
    }, [caseItem?.id]);

    useEffect(() => {
        if (!caseItem) return;
        const threadCases = Array.isArray(fullCase?.thread_cases) ? fullCase.thread_cases : [];
        const selectedCase = threadCases.find((item) => item.id === activeCaseId) || fullCase || caseItem;
        if (!selectedCase?.id) return;

        const savedNotes = localStorage.getItem(`draft_notes_${selectedCase.id}`);
        const savedResponse = localStorage.getItem(`draft_response_${selectedCase.id}`);
        setNotes(savedNotes !== null ? savedNotes : (selectedCase.notes_for_staff || ''));
        setResponse(savedResponse !== null ? savedResponse : (selectedCase.response_to_citizen || ''));
        setAssignee(selectedCase.assigned_to || '');
        setDraftSaved(savedNotes !== null || savedResponse !== null);
        setGeoLocation(selectedCase.case_metadata?.matched_value || selectedCase.location || '');
        setGeoAssembly(selectedCase.case_metadata?.assembly_constituency || selectedCase.assembly || '');

        setLoadingActivity(true);
        apiGet(`/api/cases/${selectedCase.id}/activity`)
            .then((result) => setActivities(result.activities || []))
            .catch(() => setActivities([]))
            .finally(() => setLoadingActivity(false));
    }, [caseItem?.id, activeCaseId, fullCase]);

    useEffect(() => {
        if (!activeCaseId) return;
        localStorage.setItem(`draft_notes_${activeCaseId}`, notes);
        localStorage.setItem(`draft_response_${activeCaseId}`, response);
    }, [notes, response, activeCaseId]);

    const handleGovtStateChange = useCallback((targetId, govtCase) => {
        if (!targetId) return;
        const nextStatus = govtCase?.govt_status ?? null;
        const nextRef = govtCase?.govt_reference_number ?? null;
        setFullCase((existing) => {
            if (!existing) return existing;
            const sameRoot = existing.id !== targetId
                || (existing.govt_status === nextStatus && existing.govt_reference_number === nextRef);
            const thread = existing.thread_cases;
            if (!Array.isArray(thread) || thread.length === 0) {
                if (sameRoot) return existing;
                return { ...existing, govt_status: nextStatus, govt_reference_number: nextRef };
            }
            let changed = !sameRoot;
            const nextThread = thread.map((item) => {
                if (item.id !== targetId) return item;
                if (item.govt_status === nextStatus && item.govt_reference_number === nextRef) return item;
                changed = true;
                return { ...item, govt_status: nextStatus, govt_reference_number: nextRef };
            });
            if (!changed) return existing;
            return {
                ...existing,
                thread_cases: nextThread,
                ...(existing.id === targetId ? { govt_status: nextStatus, govt_reference_number: nextRef } : {}),
            };
        });
    }, []);

    if (!caseItem) return null;

    const threadCases = Array.isArray(fullCase?.thread_cases) && fullCase.thread_cases.length
        ? fullCase.thread_cases
        : [fullCase || caseItem];
    const selectedThreadCase = threadCases.find((item) => item.id === activeCaseId) || threadCases[0];
    const current = {
        ...(fullCase || caseItem),
        ...(selectedThreadCase || {}),
        case_metadata: selectedThreadCase?.case_metadata || fullCase?.case_metadata || caseItem.case_metadata || {},
    };
    const meta = current.case_metadata || {};
    const createdAt = current.created_at ? new Date(current.created_at) : null;
    const currentStatus = (current.status || 'new').toLowerCase();
    const isUncategorised = !current.category || current.category === 'Uncategorised' || current.category === 'General';
    const isMp = isPrimaryAccount(user);
    const caseRef = current.case_ref || `#${current.id}`;
    const suggestedTriage = getSuggestedTriage(meta, current);
    const displaySummary = getCaseSummary(current, meta);
    const followupCount = 1 + (Array.isArray(meta.contact_message_events) ? meta.contact_message_events.length : 0);
    const isResolved = currentStatus === 'resolved' || currentStatus === 'completed';
    const constituency = current.mp_constituency || fullCase?.mp_constituency || user?.constituency || '';
    const followers = Array.isArray(current.followed_by) ? current.followed_by : [];
    const isFollowing = !!user?.username && followers.includes(user.username);

    // Contextual escalate/filing label, computed purely from data already
    // flowing to the parent (govt_status/reference on the active thread
    // member) — no separate state needed. The button always reads
    // "Escalate" until the complaint is actually filed with the government
    // (a reference number/terminal govt_status) — at that point there's
    // nothing left to escalate, so it becomes "View submission".
    const alreadyFiledFlag = isGovtAlreadyFiled(current);
    const hasBeenEscalated = alreadyFiledFlag || String(current.govt_status || '').toLowerCase() === 'pending_staff_submit';
    const escalateLabel = alreadyFiledFlag ? 'View submission' : 'Escalate';
    const confirmLabel = (isUncategorised && suggestedTriage?.ai_category)
        ? 'Confirm category & assign'
        : (isResolved ? 'Mark resolved' : 'Resolve');

    // Escalate always scrolls to the filing section and (re)opens the live
    // government-portal session on Needle — whether this is the first
    // escalation or the complaint was already escalated and staff is
    // coming back to continue filing. Once it's actually been filed
    // (a reference number is on record), there's no session to open —
    // just bring the existing submission into view.
    function handleEscalateClick() {
        govtSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (alreadyFiledFlag) return;
        govtSyncRef.current?.openLiveSession();
    }

    const acceptSuggestion = async () => {
        if (!suggestedTriage?.ai_category || acceptingSuggestion) return;
        setAcceptingSuggestion(true);
        try {
            try {
                await apiPatch(`/api/cases/${current.id}`, {
                    problem_domain: suggestedTriage.ai_category,
                    problem_subdomain: suggestedTriage.ai_subcategory || null,
                });
            } catch (error) {
                if (!suggestedTriage.ai_subcategory) throw error;
                // Stale/legacy subdomain suggestions can fail validation —
                // the domain alone is still worth confirming.
                await apiPatch(`/api/cases/${current.id}`, {
                    problem_domain: suggestedTriage.ai_category,
                });
            }
            await apiPatch(`/api/cases/${current.id}/status`, { status: 'in_progress' });
            const patch = {
                category: suggestedTriage.ai_category,
                problem_domain: suggestedTriage.ai_category,
                problem_subdomain: suggestedTriage.ai_subcategory || null,
                status: 'in_progress',
            };
            setFullCase((existing) => {
                if (!existing) return existing;
                const nextThreadCases = (existing.thread_cases || []).map((item) =>
                    item.id === current.id ? { ...item, ...patch } : item
                );
                const base = existing.id === current.id ? { ...existing, ...patch } : { ...existing };
                return { ...base, thread_cases: nextThreadCases };
            });
            onStatusChange(current.id, 'in_progress');
            toast.success(`Categorised as ${suggestedTriage.ai_category}`);
        } catch (error) {
            toast.error(error.message || 'Failed to apply category');
        } finally {
            setAcceptingSuggestion(false);
        }
    };

    const handleStatusChange = async (newStatus) => {
        setUpdating(newStatus);
        try {
            await apiPatch(`/api/cases/${current.id}/status`, { status: newStatus });
            setFullCase((existing) => {
                if (!existing) return existing;
                const nextThreadCases = (existing.thread_cases || []).map((item) =>
                    item.id === current.id ? { ...item, status: newStatus } : item
                );
                return { ...existing, thread_cases: nextThreadCases };
            });
            onStatusChange(current.id, newStatus);
            toast.success(`Case marked as ${newStatus}`);
        } catch {
            toast.error('Failed to update status');
        } finally {
            setUpdating(null);
        }
    };

    const saveNotes = async () => {
        setSavingNotes(true);
        try {
            await apiPatch(`/api/cases/${current.id}`, {
                notes_for_staff: notes || null,
                response_to_citizen: response || null,
            });
            setFullCase((existing) => {
                if (!existing) return existing;
                const nextThreadCases = (existing.thread_cases || []).map((item) =>
                    item.id === current.id ? { ...item, notes_for_staff: notes || null, response_to_citizen: response || null } : item
                );
                return { ...existing, thread_cases: nextThreadCases };
            });
            localStorage.removeItem(`draft_notes_${current.id}`);
            localStorage.removeItem(`draft_response_${current.id}`);
            setDraftSaved(false);
            toast.success('Notes saved');
        } catch {
            toast.error('Failed to save notes');
        } finally {
            setSavingNotes(false);
        }
    };

    const saveGeography = async () => {
        setSavingGeo(true);
        try {
            await apiPatch(`/api/cases/${current.id}`, {
                location: geoLocation || null,
                assembly: geoAssembly || null,
            });
            const refreshed = await apiGet(`/api/cases/${current.id}`);
            setFullCase((existing) => {
                const nextThreadCases = ((existing?.thread_cases) || []).map((item) =>
                    item.id === current.id
                        ? {
                            ...item,
                            location: refreshed.location || '',
                            assembly: refreshed.assembly || '',
                            case_metadata: refreshed.case_metadata || item.case_metadata || {},
                          }
                        : item
                );
                return { ...(existing || current), ...refreshed, thread_cases: nextThreadCases };
            });
            setGeoLocation(refreshed.case_metadata?.matched_value || refreshed.location || '');
            setGeoAssembly(refreshed.case_metadata?.assembly_constituency || refreshed.assembly || '');
            onStatusChange(current.id, refreshed.status || currentStatus);
            toast.success('Geography updated and locked');
        } catch {
            toast.error('Failed to save geography');
        } finally {
            setSavingGeo(false);
        }
    };

    const sendNotification = async () => {
        setNotifySending(true);
        try {
            const customMessage = response?.trim() || null;
            await apiPost(`/api/cases/${current.id}/notify/send`, {
                message: customMessage,
                response_to_citizen: customMessage,
            });
            setNotifyOpen(false);
            setNotifyInput('');
            toast.success('WhatsApp update sent — case moved to Resolved');
            onStatusChange(current.id, 'resolved');
            onClose();
        } catch (error) {
            toast.error(error.message || 'Failed to send notification');
        } finally {
            setNotifySending(false);
        }
    };

    const handleAssign = async (username) => {
        try {
            await apiPatch(`/api/cases/${current.id}`, { assigned_to: username || null });
            setAssignee(username);
            setFullCase((existing) => {
                if (!existing) return existing;
                const nextThreadCases = (existing.thread_cases || []).map((item) =>
                    item.id === current.id ? { ...item, assigned_to: username || null } : item
                );
                return { ...existing, thread_cases: nextThreadCases };
            });
            onStatusChange(current.id, currentStatus);
            toast.success(username ? `Assigned to ${username}` : 'Unassigned');
        } catch {
            toast.error('Failed to assign case');
        }
    };

    const handlePriorityChange = async (nextPriority) => {
        try {
            await apiPatch(`/api/cases/${current.id}`, { priority: nextPriority });
            setFullCase((existing) => {
                if (!existing) return existing;
                const isCritical = nextPriority === 'critical';
                const nextThreadCases = (existing.thread_cases || []).map((item) =>
                    item.id === current.id ? { ...item, priority: nextPriority, is_critical: isCritical } : item
                );
                const base = existing.id === current.id ? { ...existing, priority: nextPriority, is_critical: isCritical } : { ...existing };
                return { ...base, thread_cases: nextThreadCases };
            });
            toast.success(`Priority set to ${nextPriority}`);
        } catch {
            toast.error('Failed to update priority');
        }
    };

    const handleDelete = async () => {
        if (!window.confirm('Delete this case? This cannot be undone.')) return;
        try {
            await onDeleteCase(current.id);
            onClose();
            toast.success('Case deleted');
        } catch {
            toast.error('Failed to delete case');
        }
    };

    const toggleFollow = async () => {
        setFollowBusy(true);
        try {
            if (isFollowing) {
                await apiDelete(`/api/cases/${current.id}/follow`);
            } else {
                await apiPost(`/api/cases/${current.id}/follow`, {});
            }
            const nextFollowers = isFollowing
                ? followers.filter((u) => u !== user?.username)
                : [...followers, user?.username].filter(Boolean);
            setFullCase((existing) => {
                if (!existing) return existing;
                const nextThreadCases = (existing.thread_cases || []).map((item) =>
                    item.id === current.id ? { ...item, followed_by: nextFollowers } : item
                );
                const base = existing.id === current.id ? { ...existing, followed_by: nextFollowers } : { ...existing };
                return { ...base, thread_cases: nextThreadCases };
            });
        } catch {
            toast.error(isFollowing ? 'Failed to unfollow' : 'Failed to follow');
        } finally {
            setFollowBusy(false);
        }
    };

    const copyCaseRef = () => {
        navigator.clipboard?.writeText(caseRef);
        toast.success(`Copied ${caseRef}`);
    };

    const handleTranslate = async () => {
        const targetId = current.id;
        setTranslations((prev) => ({ ...prev, [targetId]: { ...(prev[targetId] || {}), loading: true, error: null } }));
        try {
            const result = await apiPost(`/api/cases/${targetId}/translate`, {});
            setTranslations((prev) => ({
                ...prev,
                [targetId]: {
                    loading: false,
                    translation: result.translation || null,
                    alreadyEnglish: !!result.already_english,
                    error: result.error || null,
                },
            }));
        } catch (error) {
            setTranslations((prev) => ({ ...prev, [targetId]: { loading: false, translation: null, error: error.message || 'Translation failed' } }));
        }
    };

    const defaultNotifyMessage = (() => {
        const msgs = {
            new:         `Your grievance (${caseRef}) has been received and is being reviewed.`,
            in_progress: `Update on your grievance (${caseRef}): We are actively working on this.`,
            resolved:    `Good news! Your grievance (${caseRef}) has been resolved. Reply 'NO' to reopen.`,
            completed:   `Good news! Your grievance (${caseRef}) has been resolved. Reply 'NO' to reopen.`,
            closed:      `Your grievance (${caseRef}) has been closed. Thank you for reaching out.`,
        };
        return response?.trim() || msgs[current.status] || `Update on your grievance (${caseRef}): Status is now '${current.status}'.`;
    })();

    return (
        <>
            <Sheet open={!!caseItem} onOpenChange={(open) => { if (!open) onClose(); }}>
                <SheetContent
                    side="right"
                    className="w-full md:w-[calc(100vw-96px)] md:!max-w-[1400px] p-0 flex overflow-hidden [&>button]:hidden rounded-none"
                    style={{
                        background: C.paper,
                        fontFamily: '"Inter", "Noto Sans Devanagari", system-ui, sans-serif',
                        boxShadow: 'none',
                        border: 'none',
                    }}
                >
                    {!isMobile && <CaseDetailDesignSidebar />}
                    <div style={{
                        flex: 1,
                        minWidth: 0,
                        minHeight: '100vh',
                        display: 'flex',
                        flexDirection: 'column',
                        background: C.paper,
                    }}>
                    <DrawerHeader
                        caseRef={caseRef}
                        status={currentStatus}
                        isUncategorised={isUncategorised}
                        onClose={onClose}
                        isFollowing={isFollowing}
                        onToggleFollow={toggleFollow}
                        followBusy={followBusy}
                        onCopyRef={copyCaseRef}
                    />
                    <CaseMetaRow
                        phone={current.user_phone}
                        createdAt={fullCase?.created_at ? new Date(fullCase.created_at) : createdAt}
                        language={meta.detected_language || meta.language}
                    />
                    <ComplaintTabStrip
                        threadCases={threadCases}
                        activeCaseId={activeCaseId}
                        onSelectCase={(item) => setActiveCaseId(item.id)}
                    />
                    <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', minHeight: 0 }}>
                        <CaseHero
                            current={current}
                            meta={meta}
                            priority={current.priority || (current.is_critical ? 'critical' : 'standard')}
                            onPriorityChange={handlePriorityChange}
                        />
                        <GovernmentJourneyPanel current={current} />
                        <div
                            style={{
                                display: 'grid',
                                gridTemplateColumns: isMobile ? '1fr' : 'minmax(0,1fr) 360px',
                                alignItems: 'start',
                                minHeight: '100%',
                                gap: isMobile ? 0 : 28,
                                padding: isMobile ? 0 : '0 76px 48px',
                            }}
                        >
                            <div style={{ minWidth: 0, border: isMobile ? 'none' : `1px solid ${C.hair}`, background: C.paper }}>
                                <ContactQueueNotice current={current} />

                                {isResolved ? (
                                    <ResolvedComplaintSummary
                                        current={current}
                                        meta={meta}
                                        activities={activities}
                                        loadingActivity={loadingActivity}
                                    />
                                ) : (
                                    <>
                                        {currentStatus === 'pending_review' && (
                                            <ReviewReasonBanner
                                                current={current}
                                                meta={meta}
                                                onViewSummary={() => aiSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                                            />
                                        )}
                                        <CitizenComplaintSection
                                            current={current}
                                            meta={meta}
                                            actionRow={(
                                                <ComplaintActionRow
                                                    onConfirm={() => {
                                                        if (isUncategorised && suggestedTriage?.ai_category) {
                                                            acceptSuggestion();
                                                        } else {
                                                            handleStatusChange('resolved');
                                                        }
                                                    }}
                                                    confirmLabel={confirmLabel}
                                                    onReply={() => { setNotifyInput(''); setNotifyOpen(true); }}
                                                    onEscalate={handleEscalateClick}
                                                    escalateLabel={escalateLabel}
                                                    showEscalateHint={!hasBeenEscalated}
                                                />
                                            )}
                                        />
                                        <div ref={aiSectionRef}>
                                            <AiUnderstandingSection
                                                current={current}
                                                meta={meta}
                                                displaySummary={displaySummary}
                                                followupCount={followupCount}
                                                suggestedTriage={isUncategorised ? suggestedTriage : null}
                                                onAcceptSuggestion={acceptSuggestion}
                                                accepting={acceptingSuggestion}
                                                translationState={translations[current.id]}
                                                onTranslate={handleTranslate}
                                                geoLocation={geoLocation}
                                                geoAssembly={geoAssembly}
                                                setGeoLocation={setGeoLocation}
                                                setGeoAssembly={setGeoAssembly}
                                                onSaveGeo={saveGeography}
                                                savingGeo={savingGeo}
                                                geoLocked={meta.geography_locked}
                                            />
                                        </div>
                                        <AttachmentsSection media={current.media || []} caseId={current.id} />
                                        <div ref={govtSectionRef}>
                                            <GovtSyncSection
                                                ref={govtSyncRef}
                                                caseId={current.id}
                                                isMp={isMp}
                                                onSubmitted={onStatusChange}
                                                onGovtStateChange={handleGovtStateChange}
                                            />
                                        </div>
                                        <NotesSection
                                            notes={notes}
                                            setNotes={setNotes}
                                            response={response}
                                            setResponse={setResponse}
                                            draftSaved={draftSaved}
                                            onSave={saveNotes}
                                            saving={savingNotes}
                                            phone={current.user_phone}
                                            isMp={isMp}
                                            responseSectionRef={responseSectionRef}
                                            responseInputRef={responseInputRef}
                                            onNotify={() => { setNotifyInput(''); setNotifyOpen(true); }}
                                        />
                                    </>
                                )}
                            </div>

                            <aside
                                style={{
                                    minWidth: 0,
                                    background: C.surfaceWarm,
                                    border: isMobile ? 'none' : `1px solid ${C.hair}`,
                                }}
                            >
                                <StatusActions
                                    currentStatus={currentStatus}
                                    onStatusChange={handleStatusChange}
                                    updating={updating}
                                />
                                <ActivityTimeline activities={activities} loading={loadingActivity} />
                                <CaseInformation
                                    current={current}
                                    meta={meta}
                                    caseRef={caseRef}
                                    createdAt={createdAt}
                                    assignee={assignee}
                                    constituency={constituency}
                                    onAssign={handleAssign}
                                    staff={staff}
                                    onDelete={handleDelete}
                                    userRole={user?.role}
                                    onSaveGeo={saveGeography}
                                    savingGeo={savingGeo}
                                    priority={current.priority || (current.is_critical ? 'critical' : 'standard')}
                                    onPriorityChange={handlePriorityChange}
                                />
                            </aside>
                        </div>
                    </div>

                    {!isResolved && (
                        <div style={{
                            flexShrink: 0, borderTop: `1px solid ${C.hairStrong}`,
                            display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(0,1fr) 360px',
                        }}>
                            <div style={{
                                padding: isMobile ? '12px 20px' : '12px 76px', background: C.paper,
                                display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
                            }}>
                                <button onClick={saveNotes} disabled={savingNotes} style={{
                                    padding: '10px 16px', background: 'transparent', border: `1px solid ${C.hairStrong}`, color: C.ink,
                                    fontSize: 12, fontWeight: 700, cursor: savingNotes ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
                                    display: 'inline-flex', alignItems: 'center', gap: 6,
                                }}>
                                    {savingNotes && <Loader2 size={12} className="animate-spin" />}
                                    <Icon name="doc" size={12} color={C.ink} /> Save notes
                                </button>
                                <button
                                    onClick={() => (isUncategorised && suggestedTriage?.ai_category ? acceptSuggestion() : handleStatusChange('resolved'))}
                                    style={{
                                        flex: '1 1 160px', padding: '10px 16px', background: C.green, color: '#F5EFE0', border: 'none',
                                        fontSize: 12.5, fontWeight: 700, letterSpacing: '0.02em', cursor: 'pointer', fontFamily: 'inherit',
                                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
                                    }}>
                                    <Icon name="check" size={13} color="#F5EFE0" stroke={2.5} /> {confirmLabel}
                                </button>
                                <button onClick={handleEscalateClick} style={{
                                    padding: '10px 16px', background: C.surface, color: C.saffron, border: `1px solid ${C.saffron}`,
                                    fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
                                    display: 'inline-flex', alignItems: 'center', gap: 6,
                                }}>
                                    <Icon name="unlock" size={12} color={C.saffron} stroke={2} /> {escalateLabel}
                                </button>
                                <button onClick={() => { setNotifyInput(''); setNotifyOpen(true); }} style={{
                                    padding: '10px 16px', background: 'transparent', border: `1px solid ${C.hairStrong}`, color: C.ink,
                                    fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                                    display: 'inline-flex', alignItems: 'center', gap: 6,
                                }}>
                                    <Icon name="chat" size={12} color={C.ink} /> Reply
                                </button>
                            </div>
                            {!isMobile && <div style={{ background: C.surfaceWarm, borderLeft: `1px solid ${C.hair}` }} />}
                        </div>
                    )}
                    </div>
                </SheetContent>
            </Sheet>

            <Dialog open={notifyOpen} onOpenChange={(open) => { setNotifyOpen(open); if (!open) setNotifyInput(''); }}>
                <DialogContent className="max-w-sm" style={{ background: C.paper, fontFamily: 'inherit' }}>
                    <DialogHeader>
                        <DialogTitle style={{ color: C.ink }}>Send WhatsApp Update</DialogTitle>
                        <DialogDescription style={{ color: C.ink3 }}>
                            Type <strong style={{ color: C.ink }}>{caseRef}</strong> to confirm sending a message to the citizen.
                        </DialogDescription>
                    </DialogHeader>
                    <div style={{ padding: '8px 0', display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <div style={{
                            background: C.paperDeep, border: `1px solid ${C.hair}`,
                            padding: '10px 12px', fontSize: 12.5, color: C.ink, lineHeight: 1.5,
                        }}>
                            {defaultNotifyMessage}
                        </div>
                        {response?.trim() && (
                            <p style={{ fontSize: 11, color: C.greenInk, fontWeight: 600 }}>✓ Using your custom response message</p>
                        )}
                        <Input
                            placeholder={`Type ${caseRef} to confirm`}
                            value={notifyInput}
                            onChange={(e) => setNotifyInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && notifyInput === caseRef && sendNotification()}
                            autoFocus
                        />
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => { setNotifyOpen(false); setNotifyInput(''); }}>Cancel</Button>
                        <Button
                            onClick={sendNotification}
                            disabled={notifyInput !== caseRef || notifySending}
                            style={{ background: C.green, color: '#F5EFE0', border: 'none' }}
                        >
                            {notifySending ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Send className="h-4 w-4 mr-1" />}
                            Confirm &amp; Send
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
