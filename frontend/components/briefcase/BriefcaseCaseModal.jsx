'use client';

import { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Loader2, Send } from 'lucide-react';
import { apiGet, apiPatch, apiPost, API_BASE, getAuthToken } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import BriefcaseSourceMediaViewer from '@/components/briefcase/BriefcaseSourceMediaViewer';
import { STATUS_OPTIONS } from '@/components/briefcase/briefcase-shared';
import { isPrimaryAccount } from '@/lib/account';

// ─── Icon component ─────────────────────────────────────────
function Icon({ name, size = 14, color = 'currentColor', stroke = 1.5 }) {
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
    };
    return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
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
function ReviewReasonBanner({ current, meta }) {
    const reasons = getReviewReasons(current, meta);
    return (
        <div style={{
            padding: '14px 20px',
            background: C.saffronTint,
            borderLeft: `3px solid ${C.saffron}`,
            borderBottom: `1px solid ${C.hair}`,
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
                <Icon name="warn" size={13} color={C.saffron} stroke={2} />
                <span style={{
                    fontFamily: '"JetBrains Mono", monospace', fontSize: 9.5,
                    letterSpacing: '0.16em', color: C.saffron, textTransform: 'uppercase', fontWeight: 700,
                }}>Needs review · why</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {reasons.map((reason, i) => (
                    <div key={i}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: C.ink }}>{reason.title}</div>
                        <div style={{ fontSize: 12, color: C.ink2, lineHeight: 1.5, marginTop: 2 }}>{reason.detail}</div>
                    </div>
                ))}
            </div>
        </div>
    );
}

function getSelectedThreadCaseId(fullCase, caseItem, activeCaseId) {
    const threadCases = Array.isArray(fullCase?.thread_cases) && fullCase.thread_cases.length
        ? fullCase.thread_cases
        : [fullCase || caseItem].filter(Boolean);
    return threadCases.find((item) => item.id === activeCaseId)?.id || threadCases[0]?.id || null;
}

// ─── Drawer header ───────────────────────────────────────────
function DrawerHeader({ caseRef, status, isUncategorised, onClose }) {
    const palette = {
        pending:     { bg: C.saffronTint, fg: C.saffron },
        new:         { bg: C.greenWash,   fg: C.greenInk },
        in_progress: { bg: '#E0F0FF',     fg: '#1A5276' },
        resolved:    { bg: '#D5F5E3',     fg: '#1E8449' },
        completed:   { bg: '#D5F5E3',     fg: '#1E8449' },
        closed:      { bg: C.paperDeep,   fg: C.ink3 },
    }[status] || { bg: C.saffronTint, fg: C.saffron };

    return (
        <div style={{
            position: 'sticky', top: 0, zIndex: 10,
            background: C.paper, borderBottom: `1px solid ${C.hair}`,
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 16px',
        }}>
            <button onClick={onClose} style={{
                width: 30, height: 30, border: `1px solid ${C.hair}`,
                background: 'transparent', cursor: 'pointer', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
                <Icon name="x" size={13} color={C.ink2} />
            </button>

            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', minWidth: 0 }}>
                <span style={{
                    fontFamily: '"JetBrains Mono", monospace', fontSize: 11,
                    color: C.ink3, letterSpacing: '0.08em', textTransform: 'uppercase', whiteSpace: 'nowrap',
                }}>Case {caseRef}</span>

                <span style={{
                    padding: '2px 8px', background: palette.bg, color: palette.fg,
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
                    display: 'inline-flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap',
                }}>
                    <Icon name="clock" size={10} color={palette.fg} stroke={2} />
                    {status.replace(/_/g, ' ')}
                </span>

                {isUncategorised && (
                    <span style={{
                        padding: '2px 8px', background: C.saffronTint, color: C.saffron,
                        fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
                        border: `1px dashed ${C.saffron}`, whiteSpace: 'nowrap',
                    }}>uncategorised</span>
                )}
            </div>

            <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                <button style={{
                    width: 30, height: 30, border: `1px solid ${C.hair}`,
                    background: 'transparent', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                }} title="Activity history">
                    <Icon name="history" size={13} color={C.ink2} />
                </button>
                <button style={{
                    width: 30, height: 30, border: `1px solid ${C.hair}`,
                    background: 'transparent', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                }} title="More options">
                    <Icon name="dots" size={13} color={C.ink2} />
                </button>
            </div>
        </div>
    );
}

// ─── Citizen card ─────────────────────────────────────────────
function CitizenCard({ phone, createdAt, language }) {
    const last4 = phone ? phone.slice(-4) : '??';
    const dateStr = createdAt
        ? createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
        : '–';
    const timeStr = createdAt
        ? createdAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) + ' IST'
        : '–';

    return (
        <div style={sec}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{
                    width: 44, height: 44, background: C.green, color: '#F5EFE0',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontFamily: '"JetBrains Mono", monospace', fontWeight: 700, fontSize: 11,
                    flexShrink: 0, letterSpacing: '0.04em',
                }}>···{last4}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span style={{
                            fontFamily: '"JetBrains Mono", monospace', fontSize: 12.5,
                            color: C.ink, fontWeight: 600, letterSpacing: '0.04em',
                        }}>{phone || 'Unknown'}</span>
                        <span style={{ width: 1, height: 12, background: C.hair, flexShrink: 0 }} />
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: C.ink2 }}>
                            <Icon name="whatsapp" size={11} color={C.green} /> WhatsApp
                        </span>
                        {language && (
                            <>
                                <span style={{ width: 1, height: 12, background: C.hair, flexShrink: 0 }} />
                                <span style={{
                                    fontFamily: '"JetBrains Mono", monospace', fontSize: 9.5,
                                    border: `1px solid ${C.hair}`, padding: '1px 6px', color: C.ink3,
                                }}>{language}</span>
                            </>
                        )}
                    </div>
                </div>
            </div>
            <div style={{
                marginTop: 10, paddingTop: 8, borderTop: `1px solid ${C.hair}`,
                display: 'flex', gap: 10, fontSize: 11, color: C.ink3, flexWrap: 'wrap',
            }}>
                <span style={{ ...monoLbl, marginBottom: 0, fontSize: 9.5 }}>Received</span>
                <span style={{ color: C.ink }}>{dateStr} · {timeStr}</span>
            </div>
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
            borderBottom: `1px solid ${C.hair}`,
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

// ─── Message block ────────────────────────────────────────────
function MessageBlock({ rawMessage, summary, media, caseId }) {
    const [showSummary, setShowSummary] = useState(false);
    const hasSummary = Boolean(summary);

    return (
        <div style={sec}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <span style={monoLbl}>Citizen message</span>
                {hasSummary && (
                    <div style={{ display: 'flex', border: `1px solid ${C.hair}` }}>
                        <button onClick={() => setShowSummary(false)} style={{
                            padding: '3px 10px', border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                            background: !showSummary ? C.ink : 'transparent',
                            color: !showSummary ? C.paper : C.ink2,
                            fontSize: 10.5, fontWeight: 600,
                        }}>Original</button>
                        <button onClick={() => setShowSummary(true)} style={{
                            padding: '3px 10px', border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                            background: showSummary ? C.ink : 'transparent',
                            color: showSummary ? C.paper : C.ink2,
                            fontSize: 10.5, fontWeight: 600,
                            borderLeft: `1px solid ${C.hair}`,
                        }}>Summary</button>
                    </div>
                )}
            </div>

            <div style={{
                padding: '12px 14px', background: C.paperDeep,
                borderLeft: `3px solid ${C.green}`,
                fontSize: 13.5, lineHeight: 1.6, color: C.ink, whiteSpace: 'pre-wrap',
            }}>
                {showSummary ? (summary || 'No summary available.') : (rawMessage || 'No message content.')}
            </div>

            {hasSummary && !showSummary && (
                <div style={{
                    marginTop: 8, padding: '10px 12px',
                    background: C.greenWash, border: `1px solid ${C.greenTint}`,
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
                        <Icon name="sparkle" size={10} color={C.green} stroke={2} />
                        <span style={{
                            fontFamily: '"JetBrains Mono", monospace', fontSize: 9,
                            letterSpacing: '0.14em', color: C.greenInk, textTransform: 'uppercase', fontWeight: 700,
                        }}>AI Summary</span>
                    </div>
                    <div style={{ fontSize: 12, color: C.ink, lineHeight: 1.5 }}>{summary}</div>
                </div>
            )}

            {media && media.length > 0 && (
                <div style={{ marginTop: 10 }}>
                    <BriefcaseSourceMediaViewer caseId={caseId} media={media} />
                </div>
            )}
        </div>
    );
}

// ─── Geography section ────────────────────────────────────────
function GeographySection({ geoLocation, geoAssembly, setGeoLocation, setGeoAssembly, onSave, saving, locked }) {
    const isMobile = useIsMobile();
    return (
        <div style={sec}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <span style={monoLbl}>Geography</span>
                {locked && (
                    <span style={{
                        fontSize: 10, fontWeight: 700, padding: '2px 7px',
                        background: C.greenWash, color: C.greenInk,
                        textTransform: 'uppercase', letterSpacing: '0.06em',
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                    }}>
                        <Icon name="check" size={9} color={C.greenInk} stroke={2.5} /> Manual lock
                    </span>
                )}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 10, marginBottom: 10 }}>
                <div>
                    <span style={{ ...monoLbl, marginBottom: 4 }}>Location · ward</span>
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px',
                        border: `1px solid ${C.green}`, background: C.surface,
                    }}>
                        <Icon name="pin" size={11} color={C.green} />
                        <input value={geoLocation} onChange={(e) => setGeoLocation(e.target.value)}
                            placeholder="Village / ward"
                            style={{
                                flex: 1, border: 'none', background: 'transparent', outline: 'none',
                                fontSize: 12.5, color: C.ink, fontFamily: 'inherit', minWidth: 0,
                            }} />
                    </div>
                </div>
                <div>
                    <span style={{ ...monoLbl, marginBottom: 4 }}>Assembly</span>
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px',
                        border: `1px solid ${C.hair}`, background: C.surface,
                    }}>
                        <input value={geoAssembly} onChange={(e) => setGeoAssembly(e.target.value)}
                            placeholder="Assembly constituency"
                            style={{
                                flex: 1, border: 'none', background: 'transparent', outline: 'none',
                                fontSize: 12.5, color: C.ink, fontFamily: 'inherit', minWidth: 0,
                            }} />
                    </div>
                </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <button onClick={onSave} disabled={saving} style={{
                    padding: '7px 14px', background: C.green, color: '#F5EFE0', border: 'none',
                    fontSize: 11.5, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
                    cursor: saving ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
                    display: 'inline-flex', alignItems: 'center', gap: 6, opacity: saving ? 0.7 : 1,
                }}>
                    {saving && <Loader2 size={12} className="animate-spin" />}
                    Save Geography
                </button>
                <span style={{ fontSize: 11, color: C.ink3 }}>Saving locks as a manual correction.</span>
            </div>
        </div>
    );
}

// ─── Status actions ───────────────────────────────────────────
function StatusActions({ currentStatus, onStatusChange, updating }) {
    const statusStyles = {
        new:         { background: C.greenWash,   color: C.greenInk, border: `1px solid ${C.greenTint}` },
        in_progress: { background: '#E0F0FF',      color: '#1A5276',  border: '1px solid #AED6F1' },
        resolved:    { background: '#D5F5E3',      color: '#1E8449',  border: '1px solid #A9DFBF' },
        completed:   { background: '#D5F5E3',      color: '#1E8449',  border: '1px solid #A9DFBF' },
        closed:      { background: C.paperDeep,    color: C.ink3,     border: `1px solid ${C.hair}` },
        pending:     { background: C.saffronTint,  color: C.saffron,  border: `1px solid #EDBB99` },
        irrelevant:  { background: C.paperDeep,    color: C.ink3,     border: `1px solid ${C.hair}` },
    };
    return (
        <div style={sec}>
            <span style={monoLbl}>Update status</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {STATUS_OPTIONS.filter((o) => o.value !== currentStatus).map((opt) => (
                    <button key={opt.value} onClick={() => onStatusChange(opt.value)} disabled={!!updating}
                        style={{
                            padding: '5px 12px', fontSize: 11, fontWeight: 600,
                            letterSpacing: '0.04em', cursor: updating ? 'not-allowed' : 'pointer',
                            fontFamily: 'inherit', opacity: updating ? 0.7 : 1,
                            display: 'inline-flex', alignItems: 'center', gap: 5,
                            ...(statusStyles[opt.value] || { background: C.paperDeep, color: C.ink3, border: `1px solid ${C.hair}` }),
                        }}>
                        {updating === opt.value && <Loader2 size={11} className="animate-spin" />}
                        Mark {opt.label}
                    </button>
                ))}
            </div>
        </div>
    );
}

// ─── Activity timeline ────────────────────────────────────────
function ActivityTimeline({ activities, loading }) {
    const iconFor = (action = '') => {
        if (action.includes('creat'))  return 'bolt';
        if (action.includes('translat') || action.includes('summar') || action.includes('classif')) return 'sparkle';
        if (action.includes('cluster') || action.includes('link'))  return 'cluster';
        if (action.includes('view')   || action.includes('open'))   return 'eye';
        if (action.includes('assign'))  return 'user';
        if (action.includes('notif')  || action.includes('send'))   return 'whatsapp';
        if (action.includes('escalat')) return 'escalate';
        if (action.includes('resolv') || action.includes('complet')) return 'check';
        return 'clock';
    };
    return (
        <div style={sec}>
            <span style={monoLbl}>Activity</span>
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

function PendingContactMessages({ current }) {
    const meta = current?.case_metadata || {};
    const currentEvents = Array.isArray(meta.contact_message_events) ? meta.contact_message_events : [];
    const bufferedItems = Array.isArray(current?.pending_contact_messages) ? current.pending_contact_messages : [];
    const suppressedItems = Array.isArray(current?.suppressed_contact_messages) ? current.suppressed_contact_messages : [];
    const contactThreadState = current?.contact_thread_state || meta.contact_thread_state || 'normal';
    const distinctIssueCount = Number(current?.distinct_issue_count || meta.distinct_issue_count || (1 + bufferedItems.length));

    if (currentEvents.length === 0 && bufferedItems.length === 0 && suppressedItems.length === 0) {
        return null;
    }

    const stateTone = {
        high_frequency: { fg: C.saffron, bg: C.saffronTint, label: 'High frequency contact' },
        spam_suspected: { fg: C.red, bg: '#FDEDEC', label: 'Spam suspected' },
    }[String(contactThreadState).toLowerCase()];

    return (
        <div style={sec}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
                <span style={monoLbl}>Same contact in queue</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.ink3, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                        {distinctIssueCount} issue{distinctIssueCount === 1 ? '' : 's'} in 24h
                    </span>
                    {stateTone && (
                        <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 5,
                            padding: '2px 8px',
                            background: stateTone.bg,
                            color: stateTone.fg,
                            fontSize: 10,
                            fontWeight: 700,
                            letterSpacing: '0.04em',
                            textTransform: 'uppercase',
                        }}>
                            <Icon name={contactThreadState === 'spam_suspected' ? 'warn' : 'clock'} size={10} color={stateTone.fg} stroke={2} />
                            {stateTone.label}
                        </span>
                    )}
                </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {currentEvents.map((event, idx) => (
                    <div key={`current-${idx}`} style={{
                        border: `1px solid ${C.hair}`,
                        background: C.surface,
                        padding: '10px 12px',
                    }}>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: 12,
                            marginBottom: 6,
                        }}>
                        <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.ink3, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                                {event.event_type === 'low_information_noise' ? 'Low-information follow-up' : 'Follow-up on this issue'}
                            </span>
                            <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.ink3 }}>
                                {event.created_at ? new Date(event.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''}
                            </span>
                        </div>
                        <div style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.55 }}>
                            {event.message || '—'}
                        </div>
                    </div>
                ))}

                {bufferedItems.map((item) => (
                    <div key={item.id} style={{
                        border: `1px solid ${C.greenTint}`,
                        background: C.greenWash,
                        padding: '10px 12px',
                    }}>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: 12,
                            marginBottom: 6,
                        }}>
                            <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.greenInk, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                                Distinct complaint in thread
                            </span>
                            <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.ink3 }}>
                                {item.created_at ? new Date(item.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''}
                            </span>
                        </div>
                        <div style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.55 }}>
                            {item.raw_message || '—'}
                        </div>
                        {(item.problem_subdomain || item.problem_domain) && (
                            <div style={{ marginTop: 8, fontSize: 11, color: C.ink2 }}>
                                {item.problem_subdomain || item.problem_domain}
                            </div>
                        )}
                        {Array.isArray(item.contact_message_events) && item.contact_message_events.length > 0 && (
                            <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                                {item.contact_message_events.map((event, idx) => (
                                    <div key={`${item.id}-${idx}`} style={{
                                        borderLeft: `2px solid ${C.green}`,
                                        paddingLeft: 8,
                                        fontSize: 11.5,
                                        color: C.ink2,
                                        lineHeight: 1.5,
                                    }}>
                                        {event.message || '—'}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                ))}

                {suppressedItems.map((item, idx) => (
                    <div key={`suppressed-${idx}`} style={{
                        border: `1px solid ${C.red}`,
                        background: '#FEF3F2',
                        padding: '10px 12px',
                    }}>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: 12,
                            marginBottom: 6,
                        }}>
                            <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.red, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                                Suppressed after spam threshold
                            </span>
                            <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.ink3 }}>
                                {item.created_at ? new Date(item.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''}
                            </span>
                        </div>
                        <div style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.55 }}>
                            {item.message || '—'}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

function ThreadCasesSection({ threadCases, activeCaseId, onSelectCase, onReplyCase, onQuickResolve, onEscalate, updating }) {
    if (!Array.isArray(threadCases) || threadCases.length <= 1) {
        return null;
    }

    return (
        <div style={sec}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 10, flexWrap: 'wrap' }}>
                <span style={monoLbl}>Complaints in this thread</span>
                <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.ink3, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                    {threadCases.length} real cases
                </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {threadCases.map((item, index) => {
                    const isActive = item.id === activeCaseId;
                    return (
                        <div
                            key={item.id}
                            style={{
                                border: `1px solid ${isActive ? C.green : C.hair}`,
                                background: isActive ? C.greenWash : C.surface,
                                padding: '10px 12px',
                            }}
                        >
                            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
                                <div style={{ minWidth: 0 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                                        <span style={{ fontSize: 10, fontFamily: '"JetBrains Mono", monospace', color: C.ink3, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                                            {index === 0 ? 'Latest complaint' : `Complaint +${index}`}
                                        </span>
                                        <span style={{
                                            fontSize: 10,
                                            fontWeight: 700,
                                            letterSpacing: '0.05em',
                                            textTransform: 'uppercase',
                                            color: item.status === 'resolved' || item.status === 'completed' ? '#1E8449' : C.ink2,
                                        }}>
                                            {(item.status || 'new').replace(/_/g, ' ')}
                                        </span>
                                    </div>
                                    <div style={{ marginTop: 4, fontSize: 12.5, color: C.ink, lineHeight: 1.55 }}>
                                        {item.raw_message || '—'}
                                    </div>
                                    <div style={{ marginTop: 8, display: 'flex', gap: 10, flexWrap: 'wrap', fontSize: 11, color: C.ink2 }}>
                                        <span>{item.problem_subdomain || item.problem_domain || item.category || 'Uncategorised'}</span>
                                        <span>{item.location || 'Unknown location'}</span>
                                        <span>{item.assembly || 'Unknown assembly'}</span>
                                    </div>
                                </div>
                                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                                    <button
                                        onClick={() => onSelectCase(item)}
                                        style={{
                                            padding: '5px 10px',
                                            background: isActive ? C.green : 'transparent',
                                            color: isActive ? '#F5EFE0' : C.greenInk,
                                            border: `1px solid ${C.green}`,
                                            cursor: 'pointer',
                                            fontSize: 10.5,
                                            fontWeight: 700,
                                            letterSpacing: '0.04em',
                                            textTransform: 'uppercase',
                                        }}
                                    >
                                        {isActive ? 'Open' : 'View'}
                                    </button>
                                    <button
                                        onClick={() => onReplyCase(item)}
                                        style={{
                                            padding: '5px 10px',
                                            background: 'transparent',
                                            color: C.greenInk,
                                            border: `1px solid ${C.green}`,
                                            cursor: 'pointer',
                                            fontSize: 10.5,
                                            fontWeight: 700,
                                            letterSpacing: '0.04em',
                                            textTransform: 'uppercase',
                                        }}
                                    >
                                        Reply
                                    </button>
                                    {!['resolved', 'completed', 'closed'].includes(String(item.status || '').toLowerCase()) && (
                                        <button
                                            onClick={() => onQuickResolve(item.id)}
                                            disabled={updating === `resolve-${item.id}`}
                                            style={{
                                                padding: '5px 10px',
                                                background: '#D5F5E3',
                                                color: '#1E8449',
                                                border: '1px solid #A9DFBF',
                                                cursor: updating === `resolve-${item.id}` ? 'not-allowed' : 'pointer',
                                                fontSize: 10.5,
                                                fontWeight: 700,
                                                letterSpacing: '0.04em',
                                                textTransform: 'uppercase',
                                                opacity: updating === `resolve-${item.id}` ? 0.7 : 1,
                                            }}
                                        >
                                            Resolve
                                        </button>
                                    )}
                                    {isGovtAlreadyFiled(item) ? (
                                        <span style={{
                                            padding: '5px 10px',
                                            fontSize: 10.5,
                                            fontWeight: 700,
                                            letterSpacing: '0.04em',
                                            textTransform: 'uppercase',
                                            color: C.ink2,
                                            border: `1px solid ${C.hair}`,
                                        }}>
                                            {item.govt_reference_number
                                                ? `Ref ${item.govt_reference_number}`
                                                : 'Already filed'}
                                        </span>
                                    ) : (
                                        <button
                                            type="button"
                                            onClick={() => onEscalate(item)}
                                            aria-label="Escalate"
                                            style={{
                                                padding: '5px 10px',
                                                background: C.saffron,
                                                color: '#F5EFE0',
                                                border: 'none',
                                                cursor: 'pointer',
                                                fontSize: 10.5,
                                                fontWeight: 700,
                                                letterSpacing: '0.04em',
                                                textTransform: 'uppercase',
                                            }}
                                        >
                                            Escalate
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ─── Government Department Sync ──────────────────────────────
// Staff-assisted forwarding to a state grievance portal (Rajasthan Sampark,
// UP Jansunwai, CPGRAMS). "Open live portal" launches a real browser session
// on the backend and streams it here — staff log in, the session auto-
// navigates to the grievance form once a portal's post-login path is
// configured, and staff read the AI worksheet below and type everything
// into the real page themselves (no field is auto-filled — see
// modules/govt_sync/browser_session.py's module docstring for why).
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
function GovtLiveBrowserView({ wsPath, viewport, onClose, onSessionGone }) {
    const canvasRef = useRef(null);
    const wsRef = useRef(null);
    const [connected, setConnected] = useState(false);
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
        }
    }

    function scaled(e) {
        const rect = canvasRef.current.getBoundingClientRect();
        return {
            x: Math.round(((e.clientX - rect.left) / rect.width) * vw),
            y: Math.round(((e.clientY - rect.top) / rect.height) * vh),
        };
    }

    return (
        <div style={{ marginTop: 8, marginBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 11, color: connected ? C.greenInk : C.saffron, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: connected ? C.green : C.saffron, display: 'inline-block' }} />
                    {connected ? 'Live — log in, fill in the grievance form, and click Submit yourself' : 'Connecting to live portal session…'}
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
        </div>
    );
}

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
    const [liveSession, setLiveSession] = useState(null); // { session_id, ws_path, viewport, portal_name }
    const [liveConnecting, setLiveConnecting] = useState(false);
    const liveSessionRef = useRef(null); // mirrors liveSession so the unmount cleanup below sees the latest value, not a stale closure

    useEffect(() => {
        if (!caseId) return;
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
        apiGet('/api/govt-portal').then(setResolvedPortal).catch(() => setResolvedPortal(null));
    }, []);

    useEffect(() => {
        onGovtStateChange?.(caseId, govtState?.case || null);
    }, [caseId, govtState, onGovtStateChange]);

    // Must be declared before useImperativeHandle — the dependency array
    // evaluates during render. A later `const` was a TDZ ReferenceError and
    // crashed the Briefcase case drawer (and the Vercel client bundle).
    // Live Playwright session automation defaults on (see api_router.py's
    // _govt_live_automation_enabled docstring) — this just defaults to
    // manual here too for the brief window before the first /api/govt-portal
    // fetch resolves, rather than flashing the live-session button.
    const liveAutomationEnabled = resolvedPortal?.live_automation_enabled === true;

    // Exposed so Escalate (per-complaint row, or same-row footer on
    // single-complaint cases) can trigger this section's filing flow.
    // Rebind when caseId/govtState/liveAutomationEnabled change so a thread
    // switch opens the right case and this always reflects the current
    // automation-enabled state. While live automation is off, Escalate
    // prepares the AI worksheet instead of opening a browser session —
    // same one-click entry point staff already know, different destination.
    useImperativeHandle(
        ref,
        () => ({ openLiveSession: () => (liveAutomationEnabled ? handleOpenLive() : handlePrepare()) }),
        [caseId, govtState, liveAutomationEnabled],
    );

    if (!caseId) return null;
    const status = govtState?.case?.govt_status || 'not_forwarded';
    const hasPortal = !!govtState?.case?.govt_portal_id;
    const alreadyFiled = isGovtAlreadyFiled(govtState?.case);
    const supported = resolvedPortal?.supported ?? true; // don't flash "unsupported" before the first fetch resolves

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
        toast.error('That live session ended (the server restarted since it was opened) — click "Open live portal" to start a new one');
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
            const result = await apiPost(`/api/cases/${caseId}/govt/session/start`, {});
            setLive(result);
            toast.success('Live portal session open — log in to continue');
            const refreshed = await apiGet(`/api/cases/${caseId}/govt`);
            setGovtState(refreshed);
        } catch (e) {
            setLive(null);
            toast.error(e.message || 'Could not open a live session');
        } finally {
            setLiveConnecting(false);
        }
    }

    async function handleCloseLive() {
        const session = liveSessionRef.current;
        if (!session) return;
        try {
            await apiPost(`/api/cases/${caseId}/govt/session/${session.session_id}/close`, {});
        } catch { /* best effort */ }
        setLive(null);
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
            toast.success(result.changed ? `Status updated: ${GOVT_STATUS_LABEL[result.govt_status] || result.govt_status}` : (result.note || 'No change yet'));
        } catch (e) {
            toast.error(e.message || 'Status check failed');
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
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 10, flexWrap: 'wrap' }}>
                <span style={monoLbl}>Government Portal</span>
                <span style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase',
                    padding: '2px 8px',
                    color: status === 'resolved' ? C.greenInk : status === 'rejected' ? C.red : status === 'not_forwarded' ? C.ink3 : C.saffron,
                    background: status === 'resolved' ? C.greenTint : status === 'rejected' ? '#FDEDEC' : status === 'not_forwarded' ? C.surface : C.saffronTint,
                }}>
                    {GOVT_STATUS_LABEL[status] || status}
                </span>
            </div>

            {!hasPortal && supported && !alreadyFiled && (
                <div>
                    {resolvedPortal?.portal && (
                        <div style={{ fontSize: 11.5, color: C.ink2, marginBottom: 8 }}>
                            Will file via <strong style={{ color: C.ink }}>{resolvedPortal.portal.portal_name}</strong>
                            {resolvedPortal.state ? ` (${resolvedPortal.state})` : ''} — set by this MP's constituency, not a choice here.
                            {!resolvedPortal.portal.ready && (
                                <div style={{ color: C.saffron, marginTop: 4 }}>
                                    ⚠ Portal URL confirmed, but its department list isn't mapped yet — preparing a case here will show an error until an admin sets that up.
                                </div>
                            )}
                            {!liveAutomationEnabled && (
                                <div style={{ color: C.ink3, marginTop: 4 }}>
                                    Automated filing is off — prepare the AI worksheet below, then file it on the portal yourself.
                                </div>
                            )}
                        </div>
                    )}
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                        {liveAutomationEnabled && (
                            <Button size="sm" disabled={busy || liveConnecting} onClick={handleOpenLive}>
                                {liveConnecting ? <Loader2 size={14} className="animate-spin" /> : 'Open live portal'}
                            </Button>
                        )}
                        <Button size="sm" variant={liveAutomationEnabled ? 'outline' : undefined} disabled={busy} onClick={handlePrepare}>
                            {busy ? <Loader2 size={14} className="animate-spin" /> : (liveAutomationEnabled ? 'Worksheet only' : 'Prepare worksheet')}
                        </Button>
                    </div>
                </div>
            )}

            {!hasPortal && !supported && (
                <div style={{ fontSize: 11.5, color: C.ink2, fontStyle: 'italic' }}>
                    No government portal configured yet for {resolvedPortal?.state ? `state "${resolvedPortal.state}"` : "this tenant's state (none on file)"}.
                    Ask an admin to add one under Government Portals settings.
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
                    {govtState?.case?.base_url && (
                        <a href={govtState.case.base_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11.5, color: C.green, display: 'inline-block', marginBottom: 10 }}>
                            Open {govtState.case.portal_name} to file this →
                        </a>
                    )}
                    {worksheet?.staff_action_note && (
                        <div style={{ fontSize: 11, color: C.ink2, marginBottom: 10, fontStyle: 'italic' }}>{worksheet.staff_action_note}</div>
                    )}
                    {liveAutomationEnabled && status === 'pending_staff_submit' && !alreadyFiled && !liveSession && (
                        <Button size="sm" disabled={liveConnecting} onClick={handleOpenLive} style={{ marginBottom: 4 }}>
                            {liveConnecting ? <Loader2 size={14} className="animate-spin" /> : 'Open live portal'}
                        </Button>
                    )}
                </div>
            )}

            {liveSession && (
                <div>
                    <div style={{
                        fontSize: 11.5, color: C.ink, background: C.greenWash, border: `1px solid ${C.greenTint}`,
                        padding: '8px 10px', marginBottom: 8,
                    }}>
                        Nothing on this form is auto-filled — log in, and if the portal's grievance-form page is
                        configured you'll land there automatically; otherwise navigate to it yourself. Read the
                        worksheet below and type each field in yourself.
                        <div style={{ marginTop: 4 }}>
                            <strong>Never enter the citizen's personal details</strong> (Aadhaar name, father's/spouse's
                            name, caste, gender, DOB) — Needle doesn't collect that. Where the form asks for a
                            citizen/filer name, use <strong>{liveSession.portal_filer_name || "the MP's name"}</strong> instead
                            — that's the filer of record, not the constituent. If the form offers "register
                            anonymously" or similar, leave it set to Yes.
                        </div>
                    </div>
                    <GovtLiveBrowserView
                        wsPath={liveSession.ws_path}
                        viewport={liveSession.viewport}
                        onClose={handleCloseLive}
                        onSessionGone={handleSessionGone}
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
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <Button size="sm" variant="outline" disabled={busy} onClick={handlePollNow}>
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
function AssignSection({ assignee, onAssign, staff, onDelete, userRole }) {
    const canDelete = ['mp', 'owner', 'pr'].includes(userRole);
    return (
        <div style={{ ...sec, borderBottom: 'none' }}>
            <span style={monoLbl}>Assign to</span>
            <select value={assignee} onChange={(e) => onAssign(e.target.value)} style={{
                width: '100%', border: `1px solid ${C.hair}`,
                background: C.surface, padding: '7px 10px',
                fontSize: 12.5, color: C.ink, fontFamily: 'inherit', outline: 'none', marginBottom: 14,
            }}>
                <option value="">Unassigned</option>
                {staff.map((s) => (
                    <option key={s.username} value={s.username}>
                        {s.display_name || s.username}
                    </option>
                ))}
            </select>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {canDelete && (
                    <button onClick={onDelete} style={{
                        padding: '6px 12px', border: '1px solid #F5B7B1',
                        background: '#FDEDEC', color: C.red,
                        fontSize: 11.5, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                    }}>
                        <Icon name="trash" size={12} color={C.red} /> Delete
                    </button>
                )}
            </div>
        </div>
    );
}

// ─── Sticky bottom action bar ─────────────────────────────────
function ActionBar({ onConfirm, onReply, onEscalate, isUncategorised, showEscalate }) {
    return (
        <div style={{
            position: 'sticky', bottom: 0, zIndex: 10,
            background: C.paper, borderTop: `1px solid ${C.hair}`,
            padding: '10px 16px', display: 'flex', flexDirection: 'column', gap: 8,
            boxShadow: '0 -8px 20px rgba(26,24,18,0.06)',
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <button onClick={onConfirm} style={{
                    flex: 1, padding: '10px 14px', background: C.green, color: '#F5EFE0', border: 'none',
                    fontSize: 12, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
                    cursor: 'pointer', fontFamily: 'inherit',
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
                }}>
                    <Icon name="check" size={13} color="#F5EFE0" stroke={2.5} />
                    {isUncategorised ? 'Confirm category & assign' : 'Mark resolved'}
                </button>
                {showEscalate && (
                    <button onClick={() => onEscalate()} style={{
                        padding: '10px 14px', background: C.saffron, color: '#F5EFE0', border: 'none',
                        fontSize: 12, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
                        cursor: 'pointer', fontFamily: 'inherit',
                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
                    }}>
                        <Icon name="external" size={13} color="#F5EFE0" stroke={2.5} />
                        Escalate
                    </button>
                )}
                <button onClick={onReply} style={{
                    padding: '10px 14px', background: 'transparent',
                    border: `1px solid ${C.hairStrong}`, color: C.ink,
                    fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                }}>
                    <Icon name="send" size={12} color={C.ink} /> Reply
                </button>
            </div>
        </div>
    );
}

// ─── Resolved view ────────────────────────────────────────────
function ResolvedView({ current, activities, loadingActivity, onClose }) {
    const meta = current.case_metadata || {};
    const createdAt = current.created_at ? new Date(current.created_at) : null;
    const caseRef = current.case_ref || `#${current.id}`;
    const notifyAct = [...activities].reverse().find((a) => a.action === 'citizen_notified');
    const notifiedAt = notifyAct ? new Date(notifyAct.created_at) : null;

    const fields = [
        ['Case Number', caseRef],
        ['Contact', current.user_phone || '–'],
        ['Category', current.category || 'General'],
        ['Location', meta.matched_value || current.location || '–'],
        ['Assembly', meta.assembly_constituency || current.assembly || '–'],
        ['Geo Confidence', meta.geography_confidence || '–'],
        ['Filed', createdAt ? createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '–'],
        ['Resolved', notifiedAt ? notifiedAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '–'],
    ];

    return (
        <>
            <DrawerHeader caseRef={caseRef} status="resolved" isUncategorised={false} onClose={onClose} />
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
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
                <MessageBlock rawMessage={current.raw_message} summary={meta.summary} media={current.media || []} caseId={current.id} />
                {current.response_to_citizen && (
                    <div style={sec}>
                        <span style={monoLbl}>Resolution message sent</span>
                        <div style={{
                            padding: '12px 14px', background: C.greenWash,
                            borderLeft: `3px solid ${C.green}`,
                            fontSize: 13, color: C.ink, lineHeight: 1.6,
                        }}>{current.response_to_citizen}</div>
                    </div>
                )}
                <ActivityTimeline activities={activities} loading={loadingActivity} />
            </div>
            <div style={{ background: C.paper, borderTop: `1px solid ${C.hair}`, padding: '10px 16px' }}>
                <button onClick={onClose} style={{
                    width: '100%', padding: '10px', background: 'transparent',
                    border: `1px solid ${C.hairStrong}`, color: C.ink,
                    fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
                }}>Close</button>
            </div>
        </>
    );
}

function CaseFileOverview({ current, meta, caseRef, createdAt, assignee }) {
    const infoRows = [
        ['Case number', caseRef],
        ['Priority', current.is_critical ? 'Critical' : 'Standard'],
        ['Category', current.problem_subdomain || current.problem_domain || current.category || 'Uncategorised'],
        ['Channel', 'WhatsApp'],
        ['Received', createdAt ? `${createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })} · ${createdAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} IST` : '–'],
        ['Constituency', current.assembly || meta.assembly_constituency || '–'],
        ['Location', meta.matched_value || current.location || '–'],
        ['Assignee', assignee || 'Unassigned'],
    ];

    return (
        <div style={{ ...sec, background: C.surfaceWarm }}>
            <div style={{ ...monoLbl, marginBottom: 10 }}>Case file</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {infoRows.map(([label, value], index) => (
                    <div
                        key={label}
                        style={{
                            padding: '10px 0',
                            borderTop: index === 0 ? 'none' : `1px solid ${C.hair}`,
                        }}
                    >
                        <div style={{ ...monoLbl, marginBottom: 4, fontSize: 9 }}>{label}</div>
                        <div style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.45, fontWeight: 600 }}>
                            {value}
                        </div>
                    </div>
                ))}
            </div>
        </div>
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
    const [replyIntentCaseId, setReplyIntentCaseId] = useState(null);
    const [escalateIntentCaseId, setEscalateIntentCaseId] = useState(null);
    const [geoLocation, setGeoLocation] = useState('');
    const [geoAssembly, setGeoAssembly] = useState('');
    const [savingGeo, setSavingGeo] = useState(false);
    const responseSectionRef = useRef(null);
    const responseInputRef = useRef(null);
    const govtSyncRef = useRef(null);      // imperative handle into GovtSyncSection — lets Escalate trigger its live-session flow
    const govtSectionRef = useRef(null);   // scroll target so Escalate brings that section into view

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

    useEffect(() => {
        if (!replyIntentCaseId || getSelectedThreadCaseId(fullCase, caseItem, activeCaseId) !== replyIntentCaseId) {
            return;
        }
        responseSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        if (responseInputRef.current) {
            responseInputRef.current.focus();
            const length = responseInputRef.current.value?.length || 0;
            responseInputRef.current.setSelectionRange(length, length);
        }
        setReplyIntentCaseId(null);
    }, [replyIntentCaseId, activeCaseId, fullCase, caseItem]);

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

    useEffect(() => {
        if (!escalateIntentCaseId || getSelectedThreadCaseId(fullCase, caseItem, activeCaseId) !== escalateIntentCaseId) {
            return;
        }
        const thread = Array.isArray(fullCase?.thread_cases) ? fullCase.thread_cases : [];
        const target = thread.find((item) => item.id === escalateIntentCaseId) || fullCase || caseItem;
        govtSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (!isGovtAlreadyFiled(target)) {
            govtSyncRef.current?.openLiveSession();
        }
        setEscalateIntentCaseId(null);
    }, [escalateIntentCaseId, activeCaseId, fullCase, caseItem]);

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
    const activeTab = !['resolved', 'deleted', 'clusters'].includes(String(statusFilter || '').toLowerCase());

    function handleReplyCase(item) {
        setActiveCaseId(item.id);
        setReplyIntentCaseId(item.id);
    }

    // "Escalate" = forward this grievance to the government portal. Scrolls the
    // Government Portal section into view and triggers the same live browser
    // session GovtSyncSection's own "Open live portal" button starts — staff
    // land on the portal's login page, log in themselves, get auto-navigated
    // to the grievance form where configured, then type everything in by
    // hand using the AI worksheet as reference (see browser_session.py).
    function handleEscalate(item) {
        const target = item || current;
        const targetId = target?.id || current.id;
        if (isGovtAlreadyFiled(target)) {
            if (targetId && targetId !== activeCaseId) {
                setActiveCaseId(targetId);
            }
            govtSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return;
        }
        if (targetId && targetId !== activeCaseId) {
            setActiveCaseId(targetId);
            setEscalateIntentCaseId(targetId);
            return;
        }
        govtSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        govtSyncRef.current?.openLiveSession();
    }

    const pruneResolvedThreadCase = (targetCaseId, nextStatus) => {
        const resolvedLike = ['resolved', 'completed', 'closed'].includes(String(nextStatus || '').toLowerCase());
        if (!resolvedLike || !activeTab) {
            return;
        }
        setFullCase((existing) => {
            if (!existing) return existing;
            const remainingThreadCases = (existing.thread_cases || []).filter((item) => item.id !== targetCaseId);
            if (remainingThreadCases.length === 0) {
                return existing;
            }
            return {
                ...existing,
                id: remainingThreadCases[0].id,
                case_ref: remainingThreadCases[0].case_ref,
                status: remainingThreadCases[0].status,
                raw_message: remainingThreadCases[0].raw_message,
                location: remainingThreadCases[0].location,
                assembly: remainingThreadCases[0].assembly,
                problem_domain: remainingThreadCases[0].problem_domain,
                problem_subdomain: remainingThreadCases[0].problem_subdomain,
                convergence_program_type: remainingThreadCases[0].convergence_program_type,
                case_metadata: remainingThreadCases[0].case_metadata || existing.case_metadata,
                pending_contact_count: Math.max(remainingThreadCases.length - 1, 0),
                thread_case_count: remainingThreadCases.length,
                thread_cases: remainingThreadCases,
            };
        });
        const remainingThreadCases = (fullCase?.thread_cases || []).filter((item) => item.id !== targetCaseId);
        if (remainingThreadCases.length === 0) {
            onClose();
            return;
        }
        if (activeCaseId === targetCaseId) {
            setActiveCaseId(remainingThreadCases[0].id);
        }
    };

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
            pruneResolvedThreadCase(current.id, newStatus);
            onStatusChange(current.id, newStatus);
            toast.success(`Case marked as ${newStatus}`);
        } catch {
            toast.error('Failed to update status');
        } finally {
            setUpdating(null);
        }
    };

    const handleQuickResolve = async (targetCaseId) => {
        setUpdating(`resolve-${targetCaseId}`);
        try {
            await apiPatch(`/api/cases/${targetCaseId}/status`, { status: 'resolved' });
            setFullCase((existing) => {
                if (!existing) return existing;
                const nextThreadCases = (existing.thread_cases || []).map((item) =>
                    item.id === targetCaseId ? { ...item, status: 'resolved' } : item
                );
                return { ...existing, thread_cases: nextThreadCases };
            });
            pruneResolvedThreadCase(targetCaseId, 'resolved');
            onStatusChange(targetCaseId, 'resolved');
            toast.success('Complaint marked resolved');
        } catch {
            toast.error('Failed to resolve complaint');
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

    const isResolved = currentStatus === 'resolved' || currentStatus === 'completed';

    return (
        <>
            <Sheet open={!!caseItem} onOpenChange={(open) => { if (!open) onClose(); }}>
                <SheetContent
                    side="right"
                    className="w-full sm:w-[min(1120px,calc(100vw-32px))] sm:max-w-[1120px] p-0 flex flex-col overflow-hidden [&>button]:hidden rounded-none"
                    style={{
                        background: C.paper,
                        fontFamily: '"IBM Plex Sans", "Noto Sans Devanagari", system-ui, sans-serif',
                        boxShadow: '-16px 0 40px rgba(26,24,18,0.10)',
                        border: 'none',
                    }}
                >
                    {isResolved ? (
                        <ResolvedView current={current} activities={activities} loadingActivity={loadingActivity} onClose={onClose} />
                    ) : (
                        <>
                            <DrawerHeader
                                caseRef={caseRef}
                                status={currentStatus}
                                isUncategorised={isUncategorised}
                                onClose={onClose}
                            />
                            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
                                <div
                                    style={{
                                        display: 'grid',
                                        gridTemplateColumns: isMobile ? '1fr' : 'minmax(0,1fr) 300px',
                                        alignItems: 'start',
                                        minHeight: '100%',
                                    }}
                                >
                                    <div style={{ minWidth: 0 }}>
                                        <CitizenCard
                                            phone={current.user_phone}
                                            createdAt={createdAt}
                                            language={meta.detected_language || meta.language}
                                        />
                                        {currentStatus === 'pending_review' && (
                                            <ReviewReasonBanner current={current} meta={meta} />
                                        )}
                                        {isUncategorised && suggestedTriage && (
                                            <AISuggestionBanner
                                                suggestion={suggestedTriage}
                                                onAccept={acceptSuggestion}
                                                accepting={acceptingSuggestion}
                                            />
                                        )}
                                        <MessageBlock
                                            rawMessage={current.raw_message}
                                            summary={displaySummary}
                                            media={current.media || []}
                                            caseId={current.id}
                                        />
                                        <ThreadCasesSection
                                            threadCases={threadCases}
                                            activeCaseId={activeCaseId}
                                            onSelectCase={(item) => setActiveCaseId(item.id)}
                                            onReplyCase={handleReplyCase}
                                            onQuickResolve={handleQuickResolve}
                                            onEscalate={handleEscalate}
                                            updating={updating}
                                        />
                                        <PendingContactMessages current={current} />
                                        <ActivityTimeline activities={activities} loading={loadingActivity} />
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
                                    </div>

                                    <aside
                                        style={{
                                            minWidth: 0,
                                            background: C.surfaceWarm,
                                            borderLeft: isMobile ? 'none' : `1px solid ${C.hair}`,
                                        }}
                                    >
                                        <CaseFileOverview
                                            current={current}
                                            meta={meta}
                                            caseRef={caseRef}
                                            createdAt={createdAt}
                                            assignee={assignee}
                                        />
                                        <GeographySection
                                            geoLocation={geoLocation}
                                            geoAssembly={geoAssembly}
                                            setGeoLocation={setGeoLocation}
                                            setGeoAssembly={setGeoAssembly}
                                            onSave={saveGeography}
                                            saving={savingGeo}
                                            locked={meta.geography_locked}
                                        />
                                        <StatusActions
                                            currentStatus={currentStatus}
                                            onStatusChange={handleStatusChange}
                                            updating={updating}
                                        />
                                        <AssignSection
                                            assignee={assignee}
                                            onAssign={handleAssign}
                                            staff={staff}
                                            onDelete={handleDelete}
                                            userRole={user?.role}
                                        />
                                    </aside>
                                </div>
                            </div>
                            <ActionBar
                                onConfirm={() => {
                                    if (isUncategorised && suggestedTriage?.ai_category) {
                                        acceptSuggestion();
                                    } else {
                                        handleStatusChange(isUncategorised ? 'in_progress' : 'resolved');
                                    }
                                }}
                                onReply={() => { setNotifyInput(''); setNotifyOpen(true); }}
                                onEscalate={handleEscalate}
                                isUncategorised={isUncategorised}
                                showEscalate={(!Array.isArray(threadCases) || threadCases.length <= 1) && !isGovtAlreadyFiled(current)}
                            />
                        </>
                    )}
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
