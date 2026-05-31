'use client';

import { useState } from 'react';
import {
    briefcasePalette as P,
    briefcaseFonts,
    BriefcaseIcon,
    formatBriefcaseAge,
    formatLanguageTag,
    getBriefcaseCitizenName,
} from '@/components/briefcase/briefcase-shared';

const MONO = briefcaseFonts.mono;

const STATUS_MAP = {
    new:               { fg: P.blue,      bg: P.blueTint,    icon: 'dot',     label: 'New' },
    in_progress:       { fg: P.greenInk,  bg: P.greenTint,   icon: 'sparkle', label: 'In progress' },
    pending:           { fg: P.saffron,   bg: P.saffronTint, icon: 'clock',   label: 'Pending' },
    pending_review:    { fg: P.saffron,   bg: P.saffronTint, icon: 'clock',   label: 'Needs review' },
    resolved:          { fg: P.greenInk,  bg: P.greenTint,   icon: 'check',   label: 'Resolved' },
    completed:         { fg: P.greenInk,  bg: P.greenTint,   icon: 'check',   label: 'Completed' },
    escalated:         { fg: '#fff',      bg: P.red,         icon: 'warn',    label: 'Escalated' },
    awaiting_location: { fg: P.ink,       bg: P.neutralTint, icon: 'pin',     label: 'Needs location' },
    closed:            { fg: P.ink3,      bg: P.neutralTint, icon: 'x',       label: 'Closed' },
    irrelevant:        { fg: P.ink3,      bg: P.neutralTint, icon: 'x',       label: 'Irrelevant' },
};

function StatusPill({ status }) {
    const s = STATUS_MAP[(status || '').toLowerCase()] || STATUS_MAP.new;
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '2px 8px 2px 6px',
            background: s.bg, color: s.fg,
            fontSize: 10.5, fontWeight: 600, letterSpacing: '0.02em', whiteSpace: 'nowrap',
        }}>
            <BriefcaseIcon name={s.icon} size={10} color={s.fg} stroke={2} />
            {s.label}
        </span>
    );
}

function SkeletonRows() {
    return Array.from({ length: 6 }).map((_, i) => (
        <tr key={i} style={{ borderBottom: `1px solid ${P.hair}` }}>
            <td style={{ padding: 0, width: 3 }} />
            {[38, 72, 155, 160, 130, 148, undefined, 95, 76].map((w, j) => (
                <td key={j} style={{ padding: '14px 10px' }}>
                    <div style={{ height: 10, width: w ? Math.round(w * 0.55) : '70%', background: P.hairStrong, opacity: 0.35, borderRadius: 2 }} />
                </td>
            ))}
        </tr>
    ));
}

const iconBtn = {
    width: 24, height: 24, border: 'none', background: 'transparent',
    cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: 0,
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
    const [hoverIdx, setHoverIdx] = useState(-1);

    const allSelected = cases.length > 0 && selectedIds.size === cases.length;

    const toggleAll = () => setSelectedIds(allSelected ? new Set() : new Set(cases.map((c) => c.id)));

    const toggleOne = (id) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
        });
    };

    const thStyle = {
        textAlign: 'left', padding: '8px 10px',
        fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.14em',
        color: P.ink3, textTransform: 'uppercase', fontWeight: 500,
        borderBottom: `1px solid ${P.hair}`,
    };

    return (
        <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed', minWidth: 900 }}>
                <colgroup>
                    <col style={{ width: 3 }} />
                    <col style={{ width: 38 }} />
                    <col style={{ width: 72 }} />
                    <col style={{ width: 155 }} />
                    <col style={{ width: 160 }} />
                    <col style={{ width: 130 }} />
                    <col style={{ width: 148 }} />
                    <col />
                    <col style={{ width: 95 }} />
                    <col style={{ width: 76 }} />
                </colgroup>

                <thead>
                    <tr style={{ background: P.surfaceWarm }}>
                        <th style={{ padding: 0 }} />
                        <th style={{ padding: '8px 8px 8px 12px' }}>
                            <div
                                onClick={toggleAll}
                                style={{
                                    width: 15, height: 15, cursor: 'pointer',
                                    border: `1.5px solid ${allSelected ? P.green : P.hairStrong}`,
                                    background: allSelected ? P.green : 'transparent',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                }}
                            >
                                {allSelected && <BriefcaseIcon name="check" size={11} color="#fff" stroke={2.5} />}
                            </div>
                        </th>
                        {['Ref', 'Citizen', 'Category', 'Location', 'Status', 'Message', 'Received', ''].map((h, i) => (
                            <th key={i} style={thStyle}>{h}</th>
                        ))}
                    </tr>
                </thead>

                <tbody>
                    {loading ? (
                        <SkeletonRows />
                    ) : cases.length === 0 ? (
                        <tr>
                            <td colSpan={10} style={{ padding: '56px 22px', textAlign: 'center', color: P.ink3, fontSize: 13 }}>
                                No cases found
                                {categoryFilter ? ` in "${categoryFilter}"` : ''}
                                {statusFilter && statusFilter !== 'all_cases' ? ` with status "${statusFilter}"` : ''}
                                {search ? ` matching "${search}"` : ''}.
                            </td>
                        </tr>
                    ) : cases.map((item, idx) => {
                        const selected = selectedIds.has(item.id);
                        const hover = hoverIdx === idx;
                        const isCritical = item.is_critical;
                        const clusterTag = item.case_metadata?.cluster_id;
                        const sub = item.problem_subdomain || item.problem_domain;
                        const ref = item.case_ref || `#${item.id}`;
                        const age = formatBriefcaseAge(item.created_at);
                        const lang = formatLanguageTag(item);
                        const citizen = getBriefcaseCitizenName(item);
                        const isUnknownAsm = !item.assembly || item.assembly === 'Unknown';

                        return (
                            <tr
                                key={item.id}
                                onMouseEnter={() => setHoverIdx(idx)}
                                onMouseLeave={() => setHoverIdx(-1)}
                                onClick={() => onSelectCase(item)}
                                style={{
                                    borderBottom: `1px solid ${P.hair}`,
                                    background: selected
                                        ? 'rgba(199,106,26,0.06)'
                                        : hover ? P.surfaceWarm : 'transparent',
                                    cursor: 'pointer',
                                }}
                            >
                                <td style={{
                                    padding: 0, width: 3,
                                    background: isCritical ? P.saffron : selected ? P.green : 'transparent',
                                }} />

                                <td style={{ padding: '10px 8px 10px 12px', verticalAlign: 'top' }}>
                                    <div
                                        onClick={(e) => { e.stopPropagation(); toggleOne(item.id); }}
                                        style={{
                                            width: 15, height: 15, cursor: 'pointer',
                                            border: `1.5px solid ${selected ? P.green : P.hairStrong}`,
                                            background: selected ? P.green : 'transparent',
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        }}
                                    >
                                        {selected && <BriefcaseIcon name="check" size={11} color="#fff" stroke={2.5} />}
                                    </div>
                                </td>

                                <td style={{ padding: '10px 8px', fontFamily: MONO, fontSize: 10, color: P.ink3, verticalAlign: 'top' }}>
                                    {ref}
                                </td>

                                <td style={{ padding: '10px 10px', verticalAlign: 'top' }}>
                                    <div style={{ fontSize: 12.5, color: P.ink, fontWeight: 600, lineHeight: 1.2 }}>
                                        {citizen}
                                    </div>
                                    <button
                                        onClick={(e) => { e.stopPropagation(); onOpenContact && onOpenContact(item.user_phone); }}
                                        style={{
                                            background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                                            fontSize: 10.5, color: P.ink3, fontFamily: MONO, marginTop: 2,
                                        }}
                                    >
                                        {item.user_phone || '—'}
                                    </button>
                                </td>

                                <td style={{ padding: '10px 10px', verticalAlign: 'top' }}>
                                    {sub ? (
                                        <div style={{ fontSize: 12, color: P.ink, fontWeight: 500 }}>{sub}</div>
                                    ) : (
                                        <span style={{
                                            display: 'inline-flex', padding: '1px 7px',
                                            background: P.saffronTint, color: P.saffron,
                                            fontSize: 10.5, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase',
                                        }}>Uncategorised</span>
                                    )}
                                    <div style={{ fontSize: 10, color: P.ink3, marginTop: 2, fontFamily: MONO, letterSpacing: '0.04em' }}>
                                        {item.category || '—'}
                                    </div>
                                </td>

                                <td style={{ padding: '10px 10px', verticalAlign: 'top' }}>
                                    <div style={{ fontSize: 12, color: P.ink, fontWeight: 500 }}>
                                        {item.location || '—'}
                                    </div>
                                    <div style={{
                                        fontSize: 10, fontFamily: MONO, marginTop: 2, letterSpacing: '0.04em',
                                        color: isUnknownAsm ? P.saffron : P.ink3,
                                    }}>
                                        {item.assembly || 'Unknown'}
                                    </div>
                                </td>

                                <td style={{ padding: '10px 10px', verticalAlign: 'top' }}>
                                    <StatusPill status={item.status} />
                                    {clusterTag && (
                                        <div style={{
                                            marginTop: 5, display: 'inline-flex', alignItems: 'center', gap: 4,
                                            fontSize: 9.5, color: P.greenInk, fontFamily: MONO,
                                            background: P.greenTint, padding: '1px 5px', fontWeight: 600,
                                        }}>
                                            <BriefcaseIcon name="cluster" size={9} color={P.greenInk} stroke={1.8} />
                                            {clusterTag}
                                        </div>
                                    )}
                                </td>

                                <td style={{ padding: '10px 10px', verticalAlign: 'top' }}>
                                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                                        <span style={{
                                            fontFamily: MONO, fontSize: 9, color: P.ink3,
                                            border: `1px solid ${P.hair}`, padding: '0 4px',
                                            flex: '0 0 auto', marginTop: 1, letterSpacing: '0.04em',
                                        }}>{lang}</span>
                                        <div style={{
                                            fontSize: 12, color: P.ink, lineHeight: 1.35,
                                            overflow: 'hidden', display: '-webkit-box',
                                            WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                                        }}>
                                            {item.raw_message || '—'}
                                        </div>
                                    </div>
                                </td>

                                <td style={{ padding: '10px 10px', verticalAlign: 'top', whiteSpace: 'nowrap' }}>
                                    <div style={{ fontFamily: MONO, fontSize: 11, color: P.ink2 }}>{age} ago</div>
                                </td>

                                <td style={{ padding: '10px 12px 10px 6px', verticalAlign: 'top', textAlign: 'right' }}>
                                    <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end', opacity: hover ? 1 : 0 }}>
                                        <button
                                            title="Assign"
                                            onClick={(e) => e.stopPropagation()}
                                            style={iconBtn}
                                        >
                                            <BriefcaseIcon name="assign" size={13} color={P.ink2} />
                                        </button>
                                        <button
                                            title="Open"
                                            onClick={(e) => { e.stopPropagation(); onSelectCase(item); }}
                                            style={iconBtn}
                                        >
                                            <BriefcaseIcon name="chevr" size={13} color={P.ink2} />
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}
