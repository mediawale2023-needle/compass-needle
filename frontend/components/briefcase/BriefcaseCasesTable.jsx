'use client';

import { useState } from 'react';
import { CheckCircle } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import {
    briefcaseFonts,
    briefcasePalette as P,
    BriefcaseIcon,
    BriefcaseStatusPill,
    formatBriefcaseAge,
    formatLanguageTag,
    getBriefcaseCitizenName,
} from '@/components/briefcase/briefcase-shared';

const { mono: MONO } = briefcaseFonts;

function getSlaLabel(caseItem) {
    const status = (caseItem.status || '').toLowerCase();
    if (status === 'resolved') {
        return { label: '— closed', color: P.ink3 };
    }
    if (!caseItem.created_at) {
        return { label: 'SLA tracking', color: P.ink2 };
    }
    const hours = (Date.now() - new Date(caseItem.created_at).getTime()) / 3600000;
    if (hours >= 24 || status === 'escalated') {
        return { label: '⚠ SLA BREACH', color: P.red, bold: true };
    }
    const remaining = Math.max(1, Math.round(24 - hours));
    return { label: `SLA ${remaining}h`, color: P.ink2 };
}

function CaseRow({ caseItem, hover, onHover, onOpenContact, onSelectCase, selected, setSelectedIds }) {
    const meta = caseItem.case_metadata || {};
    const status = (caseItem.status || '').toLowerCase();
    const isUncategorised = !caseItem.category || /general|uncategor/i.test(String(caseItem.category));
    const languageTag = formatLanguageTag(caseItem);
    const translation = meta.english_translation || meta.translated_text || meta.summary || '';
    const sla = getSlaLabel(caseItem);
    const focus = caseItem.is_critical || ['pending_review', 'awaiting_location', 'escalated'].includes(status);

    return (
        <tr
            onMouseEnter={onHover}
            onMouseLeave={() => onHover(false)}
            style={{
                borderBottom: `1px solid ${P.hair}`,
                background: selected ? 'rgba(199,106,26,0.06)' : (hover ? P.surfaceWarm : 'transparent'),
                cursor: 'pointer',
            }}
            onClick={() => onSelectCase(caseItem)}
        >
            <td style={{ padding: 0, width: 3, background: focus ? P.saffron : 'transparent' }} />
            <td style={{ padding: '10px 8px 10px 12px', width: 28, verticalAlign: 'top' }}>
                <div
                    onClick={(event) => {
                        event.stopPropagation();
                        setSelectedIds((current) => {
                            const next = new Set(current);
                            if (next.has(caseItem.id)) {
                                next.delete(caseItem.id);
                            } else {
                                next.add(caseItem.id);
                            }
                            return next;
                        });
                    }}
                    style={{
                        width: 15,
                        height: 15,
                        border: `1.5px solid ${selected ? P.green : P.hairStrong}`,
                        background: selected ? P.green : 'transparent',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}
                >
                    {selected && <BriefcaseIcon name="check" size={11} color="#fff" stroke={2.5} />}
                </div>
            </td>
            <td style={{ padding: '10px 8px', fontFamily: MONO, fontSize: 10.5, color: P.ink3, verticalAlign: 'top' }}>
                #{caseItem.id}
            </td>
            <td style={{ padding: '10px 10px', verticalAlign: 'top' }}>
                <div style={{ fontSize: 12.5, color: P.ink, fontWeight: 600, lineHeight: 1.2 }}>{getBriefcaseCitizenName(caseItem)}</div>
                <button
                    style={{
                        fontSize: 10.5,
                        color: P.ink3,
                        fontFamily: MONO,
                        marginTop: 2,
                        border: 'none',
                        background: 'transparent',
                        padding: 0,
                        cursor: 'pointer',
                        textAlign: 'left',
                    }}
                    onClick={(event) => {
                        event.stopPropagation();
                        if (caseItem.user_phone) {
                            onOpenContact(caseItem.user_phone);
                        }
                    }}
                >
                    {caseItem.user_phone || caseItem.user_id || '—'}
                </button>
            </td>
            <td style={{ padding: '10px 10px', verticalAlign: 'top' }}>
                <div
                    style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 5,
                        padding: isUncategorised ? '1px 7px' : 0,
                        background: isUncategorised ? P.saffronTint : 'transparent',
                        fontSize: isUncategorised ? 10.5 : 12,
                        color: isUncategorised ? P.saffron : P.ink,
                        fontWeight: isUncategorised ? 700 : 500,
                        letterSpacing: isUncategorised ? '0.04em' : 0,
                        textTransform: isUncategorised ? 'uppercase' : 'none',
                    }}
                >
                    {isUncategorised ? 'Uncategorised' : (meta.problem_subdomain || caseItem.subcategory || 'General')}
                </div>
                <div style={{ fontSize: 10, color: P.ink3, marginTop: 2, fontFamily: MONO, letterSpacing: '0.04em' }}>
                    {isUncategorised
                        ? `AI suggests: ${meta.problem_domain || meta.category_suggestion || 'Pending review'}`
                        : String(caseItem.category || 'General').replace('Infrastructure & Utilities', 'Infra & Utilities')}
                </div>
            </td>
            <td style={{ padding: '10px 10px', verticalAlign: 'top' }}>
                <div style={{ fontSize: 12, color: P.ink, fontWeight: 500 }}>{caseItem.location || meta.matched_value || 'Unknown'}</div>
                <div
                    style={{
                        fontSize: 10,
                        color: !caseItem.assembly ? P.saffron : P.ink3,
                        fontFamily: MONO,
                        marginTop: 2,
                        letterSpacing: '0.04em',
                    }}
                >
                    {caseItem.assembly || meta.assembly_constituency || 'Unknown'}
                </div>
            </td>
            <td style={{ padding: '10px 10px', verticalAlign: 'top' }}>
                <BriefcaseStatusPill status={caseItem.status} />
                {(caseItem.cluster_id || meta.cluster_id) && (
                    <div
                        style={{
                            marginTop: 5,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            fontSize: 9.5,
                            color: P.greenInk,
                            fontFamily: MONO,
                            background: P.greenTint,
                            padding: '1px 5px',
                            fontWeight: 600,
                        }}
                    >
                        <BriefcaseIcon name="cluster" size={9} color={P.greenInk} stroke={1.8} /> {caseItem.cluster_id || meta.cluster_id}
                    </div>
                )}
            </td>
            <td style={{ padding: '10px 10px', verticalAlign: 'top' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                    <span
                        style={{
                            fontFamily: MONO,
                            fontSize: 9,
                            color: P.ink3,
                            border: `1px solid ${P.hair}`,
                            padding: '0 4px',
                            flex: '0 0 auto',
                            marginTop: 1,
                            letterSpacing: '0.04em',
                        }}
                    >
                        {languageTag}
                    </span>
                    <div style={{ minWidth: 0, flex: 1 }}>
                        <div
                            style={{
                                fontSize: 12,
                                color: P.ink,
                                lineHeight: 1.35,
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                            }}
                        >
                            {caseItem.raw_message || 'No message available.'}
                        </div>
                        {translation && languageTag !== 'EN' && (
                            <div
                                style={{
                                    fontSize: 10.5,
                                    color: P.ink3,
                                    fontStyle: 'italic',
                                    marginTop: 3,
                                    lineHeight: 1.3,
                                    display: '-webkit-box',
                                    WebkitLineClamp: 1,
                                    WebkitBoxOrient: 'vertical',
                                    overflow: 'hidden',
                                }}
                            >
                                EN · {translation}
                            </div>
                        )}
                    </div>
                </div>
            </td>
            <td style={{ padding: '10px 10px', verticalAlign: 'top', whiteSpace: 'nowrap' }}>
                <div style={{ fontFamily: MONO, fontSize: 11, color: P.ink2 }}>{formatBriefcaseAge(caseItem.created_at)} ago</div>
                <div
                    style={{
                        fontFamily: MONO,
                        fontSize: 10,
                        color: sla.color,
                        fontWeight: sla.bold ? 700 : 400,
                        marginTop: 2,
                    }}
                >
                    {sla.label}
                </div>
            </td>
            <td style={{ padding: '10px 12px 10px 6px', verticalAlign: 'top', textAlign: 'right' }}>
                <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end', opacity: hover ? 1 : 0.55 }}>
                    <button
                        title="Open contact"
                        style={iconButtonStyle}
                        onClick={(event) => {
                            event.stopPropagation();
                            if (caseItem.user_phone) {
                                onOpenContact(caseItem.user_phone);
                            }
                        }}
                    >
                        <BriefcaseIcon name="assign" size={13} color={P.ink2} />
                    </button>
                    <button title="Translate" style={iconButtonStyle} onClick={(event) => event.stopPropagation()}>
                        <BriefcaseIcon name="translate" size={13} color={P.ink2} />
                    </button>
                    <button title="Open case" style={iconButtonStyle} onClick={(event) => { event.stopPropagation(); onSelectCase(caseItem); }}>
                        <BriefcaseIcon name="chevr" size={13} color={P.ink2} />
                    </button>
                </div>
            </td>
        </tr>
    );
}

const iconButtonStyle = {
    width: 24,
    height: 24,
    border: 'none',
    background: 'transparent',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 0,
};

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
}) {
    const [hoverIndex, setHoverIndex] = useState(-1);

    if (loading) {
        return (
            <div className="space-y-3 py-6 px-6">
                {[1, 2, 3, 4, 5].map((i) => (
                    <div key={i} className="flex items-center gap-4">
                        <Skeleton className="h-4 w-4" />
                        <Skeleton className="h-4 w-12" />
                        <Skeleton className="h-4 w-24" />
                        <Skeleton className="h-4 w-32" />
                        <Skeleton className="h-4 w-24" />
                        <Skeleton className="h-4 w-20" />
                        <Skeleton className="h-6 w-20" />
                        <Skeleton className="h-4 flex-1" />
                    </div>
                ))}
            </div>
        );
    }

    if (cases.length === 0) {
        return (
            <div className="text-center py-16">
                <CheckCircle className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
                <p className="text-muted-foreground">
                    No cases found{categoryFilter ? ` in "${categoryFilter}"` : ''}
                    {statusFilter !== 'needs' ? ` with status "${statusFilter}"` : ''}
                    {search ? ` matching "${search}"` : ''}.
                </p>
            </div>
        );
    }

    return (
        <section style={{ background: P.surface, borderTop: 'none', flex: 1, minHeight: 0, overflow: 'hidden' }}>
            <div className="md:hidden" style={{ padding: '10px 12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                {cases.map((caseItem) => {
                    const meta = caseItem.case_metadata || {};
                    const status = (caseItem.status || '').toLowerCase();
                    const isUncategorised = !caseItem.category || /general|uncategor/i.test(String(caseItem.category));
                    const languageTag = formatLanguageTag(caseItem);
                    const sla = getSlaLabel(caseItem);
                    const focus = caseItem.is_critical || ['pending_review', 'awaiting_location', 'escalated'].includes(status);
                    const translation = meta.english_translation || meta.translated_text || meta.summary || '';
                    const selected = selectedIds.has(caseItem.id);
                    return (
                        <article
                            key={caseItem.id}
                            onClick={() => onSelectCase(caseItem)}
                            style={{
                                border: `1px solid ${focus ? P.saffron : P.hair}`,
                                background: selected ? P.surfaceWarm : P.paper,
                                padding: '12px 12px 10px',
                                cursor: 'pointer',
                            }}
                        >
                            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                                <button
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        setSelectedIds((current) => {
                                            const next = new Set(current);
                                            if (next.has(caseItem.id)) next.delete(caseItem.id);
                                            else next.add(caseItem.id);
                                            return next;
                                        });
                                    }}
                                    style={{
                                        width: 18,
                                        height: 18,
                                        marginTop: 2,
                                        border: `1.5px solid ${selected ? P.green : P.hairStrong}`,
                                        background: selected ? P.green : 'transparent',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        flex: '0 0 auto',
                                    }}
                                >
                                    {selected && <BriefcaseIcon name="check" size={11} color="#fff" stroke={2.5} />}
                                </button>
                                <div style={{ minWidth: 0, flex: 1 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                                        <div style={{ fontFamily: MONO, fontSize: 10, color: P.ink3 }}>#{caseItem.id}</div>
                                        <BriefcaseStatusPill status={caseItem.status} />
                                    </div>
                                    <div style={{ fontSize: 13, color: P.ink, fontWeight: 600, marginTop: 4 }}>
                                        {getBriefcaseCitizenName(caseItem)}
                                    </div>
                                    <button
                                        style={{
                                            fontSize: 10.5,
                                            color: P.ink3,
                                            fontFamily: MONO,
                                            marginTop: 2,
                                            border: 'none',
                                            background: 'transparent',
                                            padding: 0,
                                            cursor: 'pointer',
                                            textAlign: 'left',
                                        }}
                                        onClick={(event) => {
                                            event.stopPropagation();
                                            if (caseItem.user_phone) onOpenContact(caseItem.user_phone);
                                        }}
                                    >
                                        {caseItem.user_phone || caseItem.user_id || '—'}
                                    </button>
                                </div>
                            </div>

                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
                                <span
                                    style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: 5,
                                        padding: isUncategorised ? '2px 7px' : 0,
                                        background: isUncategorised ? P.saffronTint : 'transparent',
                                        fontSize: isUncategorised ? 10.5 : 11.5,
                                        color: isUncategorised ? P.saffron : P.ink,
                                        fontWeight: isUncategorised ? 700 : 600,
                                        letterSpacing: isUncategorised ? '0.04em' : 0,
                                        textTransform: isUncategorised ? 'uppercase' : 'none',
                                    }}
                                >
                                    {isUncategorised ? 'Uncategorised' : (meta.problem_subdomain || caseItem.subcategory || 'General')}
                                </span>
                                <span style={{ fontFamily: MONO, fontSize: 9.5, color: P.ink3 }}>{caseItem.location || meta.matched_value || 'Unknown'}</span>
                                <span style={{ fontFamily: MONO, fontSize: 9.5, color: P.ink3 }}>{formatBriefcaseAge(caseItem.created_at)} ago</span>
                            </div>

                            <div style={{ marginTop: 8, fontSize: 12, color: P.ink, lineHeight: 1.4 }}>
                                {caseItem.raw_message || 'No message available.'}
                            </div>
                            {translation && languageTag !== 'EN' && (
                                <div style={{ fontSize: 10.5, color: P.ink3, fontStyle: 'italic', marginTop: 4, lineHeight: 1.35 }}>
                                    EN · {translation}
                                </div>
                            )}

                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginTop: 10 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                                    <span
                                        style={{
                                            fontFamily: MONO,
                                            fontSize: 9,
                                            color: P.ink3,
                                            border: `1px solid ${P.hair}`,
                                            padding: '0 4px',
                                            letterSpacing: '0.04em',
                                        }}
                                    >
                                        {languageTag}
                                    </span>
                                    <span style={{ fontFamily: MONO, fontSize: 10, color: sla.color, fontWeight: sla.bold ? 700 : 400 }}>
                                        {sla.label}
                                    </span>
                                </div>
                                <div style={{ display: 'flex', gap: 8 }}>
                                    <button
                                        title="Open contact"
                                        style={iconButtonStyle}
                                        onClick={(event) => {
                                            event.stopPropagation();
                                            if (caseItem.user_phone) onOpenContact(caseItem.user_phone);
                                        }}
                                    >
                                        <BriefcaseIcon name="assign" size={13} color={P.ink2} />
                                    </button>
                                    <button title="Open case" style={iconButtonStyle} onClick={(event) => { event.stopPropagation(); onSelectCase(caseItem); }}>
                                        <BriefcaseIcon name="chevr" size={13} color={P.ink2} />
                                    </button>
                                </div>
                            </div>
                        </article>
                    );
                })}
            </div>

            <div className="hidden md:block">
                <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
                    <colgroup>
                        <col style={{ width: 3 }} />
                        <col style={{ width: 38 }} />
                        <col style={{ width: 64 }} />
                        <col style={{ width: 150 }} />
                        <col style={{ width: 165 }} />
                        <col style={{ width: 130 }} />
                        <col style={{ width: 145 }} />
                        <col />
                        <col style={{ width: 105 }} />
                        <col style={{ width: 88 }} />
                    </colgroup>
                    <thead>
                        <tr style={{ background: P.surfaceWarm }}>
                            <th style={{ padding: 0 }} />
                            <th style={{ padding: '8px 8px 8px 12px' }}>
                                <div style={{ width: 15, height: 15, border: `1.5px solid ${P.hairStrong}` }} />
                            </th>
                            {['Ref', 'Citizen', 'Category', 'Location', 'Status', 'Message', 'Received / SLA', ''].map((heading) => (
                                <th
                                    key={heading}
                                    style={{
                                        textAlign: 'left',
                                        padding: '8px 10px',
                                        fontFamily: MONO,
                                        fontSize: 9.5,
                                        letterSpacing: '0.14em',
                                        color: P.ink3,
                                        textTransform: 'uppercase',
                                        fontWeight: 500,
                                        borderBottom: `1px solid ${P.hair}`,
                                    }}
                                >
                                    {heading}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {cases.map((caseItem, index) => (
                            <CaseRow
                                key={caseItem.id}
                                caseItem={caseItem}
                                hover={hoverIndex === index}
                                onHover={(value) => setHoverIndex(value ? index : -1)}
                                onOpenContact={onOpenContact}
                                onSelectCase={onSelectCase}
                                selected={selectedIds.has(caseItem.id)}
                                setSelectedIds={setSelectedIds}
                            />
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
}
