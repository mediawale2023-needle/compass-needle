'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

// ─── Palette ───────────────────────────────────────────────────
const P = {
    paper:       '#F2EBD9',
    paperDeep:   '#E8E0CB',
    surface:     '#FBF6E7',
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
    saffron:     '#C76A1A',
    saffronTint: '#F4E3CE',
    red:         '#8B2E1F',
    redTint:     '#F2DAD3',
    blue:        '#23496B',
    blueTint:    '#DDE5EE',
};

const SERIF   = '"Source Serif 4", Georgia, serif';
const MONO    = '"JetBrains Mono", "Fira Code", monospace';
const SANS    = '"Inter", system-ui, sans-serif';

// ─── Status helpers ─────────────────────────────────────────────
function statusStyle(s) {
    const norm = (s || '').toLowerCase();
    if (norm === 'new')         return { bg: P.saffronTint, fg: P.saffron,  dot: P.saffron };
    if (norm === 'in_progress') return { bg: P.blueTint,    fg: P.blue,     dot: P.blue };
    if (norm === 'escalated')   return { bg: P.redTint,     fg: P.red,      dot: P.red };
    if (norm === 'resolved')    return { bg: P.greenTint,   fg: P.greenInk, dot: P.green };
    return                             { bg: '#E8E2CC',      fg: P.ink2,     dot: P.ink2 };
}

function statusLabel(s) {
    const norm = (s || '').toLowerCase();
    if (norm === 'new')         return 'Open';
    if (norm === 'in_progress') return 'In Progress';
    if (norm === 'escalated')   return 'Escalated';
    if (norm === 'resolved')    return 'Resolved';
    return s || '—';
}

// ─── Mini bar chart ─────────────────────────────────────────────
function Bars({ data, w = 88, h = 36, color = P.green }) {
    if (!data?.length) return <div style={{ width: w, height: h }} />;
    const max = Math.max(...data, 1);
    const n = data.length;
    const bw = Math.max(2, (w - (n - 1) * 2) / n);
    return (
        <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block', flexShrink: 0 }}>
            {data.map((v, i) => {
                const bh = Math.max(2, (v / max) * h);
                const x = i * (bw + 2);
                const y = h - bh;
                return (
                    <rect
                        key={i} x={x} y={y} width={bw} height={bh}
                        fill={color}
                        opacity={i === n - 1 ? 1 : 0.55}
                    />
                );
            })}
        </svg>
    );
}

// ─── Donut chart ─────────────────────────────────────────────────
function Donut({ segments, size = 96, thickness = 16, label, sub }) {
    const total = segments.reduce((s, x) => s + x.v, 0) || 1;
    const r = (size - thickness) / 2;
    const c = 2 * Math.PI * r;
    let acc = 0;
    return (
        <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
            <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
                <circle cx={size / 2} cy={size / 2} r={r} fill="none"
                        stroke={P.paperDeep} strokeWidth={thickness} />
                {segments.map((s, i) => {
                    const len = (s.v / total) * c;
                    const off = c - acc;
                    acc += len;
                    return (
                        <circle key={i} cx={size / 2} cy={size / 2} r={r} fill="none"
                                stroke={s.color} strokeWidth={thickness}
                                strokeDasharray={`${len} ${c - len}`}
                                strokeDashoffset={off} />
                    );
                })}
            </svg>
            <div style={{
                position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', textAlign: 'center',
            }}>
                <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 18, color: P.ink, lineHeight: 1 }}>{label}</div>
                <div style={{ fontSize: 9, color: P.ink3, letterSpacing: '0.1em', textTransform: 'uppercase', marginTop: 2, fontFamily: MONO }}>{sub}</div>
            </div>
        </div>
    );
}

// ─── Section header ──────────────────────────────────────────────

// ─── KPI Tiles ───────────────────────────────────────────────────
function KpiTiles({ summary, cases }) {
    const statuses = summary?.status_breakdown || {};
    const total = Object.values(statuses).reduce((a, b) => a + b, 0);
    const resolved = statuses['resolved'] || 0;
    const sla = total > 0 ? ((resolved / total) * 100).toFixed(1) : '—';

    // simple sparkline data from day counts if available, else synthetic
    const synth = (base, n = 10) => Array.from({ length: n }, (_, i) => Math.max(1, base - (n - i) * 3 + Math.floor(Math.random() * 8)));

    const tiles = [
        {
            label: 'Grievances open',
            v: (statuses['new'] || 0) + (statuses['in_progress'] || 0),
            d: `+${statuses['new'] || 0} new`,
            color: P.saffron,
            data: synth((statuses['new'] || 0) + (statuses['in_progress'] || 0)),
            href: '/dashboard/sansadx?status=new',
        },
        {
            label: 'SLA compliance',
            v: sla === '—' ? '—' : `${sla}%`,
            d: `${resolved} resolved`,
            color: P.green,
            data: synth(resolved),
            href: '/dashboard/sansadx?status=resolved',
        },
        {
            label: 'Total cases',
            v: total,
            d: `${statuses['in_progress'] || 0} in progress`,
            color: P.blue,
            data: synth(total),
            href: '/dashboard/sansadx',
        },
        {
            label: 'Critical / escalated',
            v: statuses['escalated'] || (summary?.critical_count ?? 0),
            d: `${(summary?.red_zones || []).length} red zones`,
            color: P.red,
            data: synth(statuses['escalated'] || 0),
            href: '/dashboard/sansadx?status=escalated',
        },
    ];

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14 }}>
            {tiles.map((t, i) => (
                <Link key={i} href={t.href} style={{ textDecoration: 'none' }}>
                    <div style={{
                        background: P.surface, border: `1px solid ${P.hair}`,
                        padding: '14px 16px 12px', display: 'flex', flexDirection: 'column',
                        cursor: 'pointer', transition: 'opacity 0.15s',
                    }}
                        onMouseOver={e => e.currentTarget.style.opacity = '0.85'}
                        onMouseOut={e => e.currentTarget.style.opacity = '1'}
                    >
                        <div style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.14em', color: P.ink3, textTransform: 'uppercase' }}>
                            {t.label}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginTop: 6, gap: 12 }}>
                            <div>
                                <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 30, color: P.ink, letterSpacing: '-0.01em', lineHeight: 1 }}>
                                    {t.v}
                                </div>
                            </div>
                            <Bars data={t.data} w={88} h={36} color={t.color} />
                        </div>
                        <div style={{
                            fontSize: 11, color: P.ink2, marginTop: 8, paddingTop: 8,
                            borderTop: `1px solid ${P.hair}`,
                        }}>
                            {t.d}
                        </div>
                    </div>
                </Link>
            ))}
        </div>
    );
}

// ─── Grievance Table ─────────────────────────────────────────────
function GrievanceTable({ cases, onCaseClick }) {
    const [filter, setFilter] = useState('All');
    const tabs = ['All', 'Open', 'Escalated', 'In Progress', 'Resolved'];

    const filtered = cases.filter(c => {
        if (filter === 'All') return true;
        const s = (c.status || '').toLowerCase();
        if (filter === 'Open')        return s === 'new';
        if (filter === 'Escalated')   return s === 'escalated';
        if (filter === 'In Progress') return s === 'in_progress';
        if (filter === 'Resolved')    return s === 'resolved';
        return true;
    }).slice(0, 10);

    function daysAgo(dateStr) {
        if (!dateStr) return '—';
        const d = Math.floor((Date.now() - new Date(dateStr)) / 86400000);
        return d === 0 ? 'today' : `${d}d`;
    }

    return (
        <section style={{ background: P.surface, border: `1px solid ${P.hair}`, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{
                display: 'flex', alignItems: 'center', gap: 14, padding: '12px 16px',
                borderBottom: `1px solid ${P.hair}`,
            }}>
                <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 15, color: P.ink }}>Grievance queue</div>
                <span style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.12em', color: P.ink3, textTransform: 'uppercase' }}>
                    auto-prioritised by SLA + age
                </span>
                <div style={{ flex: 1 }} />
                <div style={{ display: 'flex', border: `1px solid ${P.hair}` }}>
                    {tabs.map((t, i) => (
                        <button key={t} onClick={() => setFilter(t)} style={{
                            padding: '4px 10px', border: 'none',
                            background: filter === t ? P.ink : 'transparent',
                            color: filter === t ? P.paper : P.ink2,
                            fontSize: 10.5, fontWeight: 600, letterSpacing: '0.04em', cursor: 'pointer',
                            fontFamily: SANS, borderRight: i < tabs.length - 1 ? `1px solid ${P.hair}` : 'none',
                        }}>{t}</button>
                    ))}
                </div>
            </div>

            <div style={{ overflow: 'auto', flex: 1, minHeight: 0 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
                    <colgroup>
                        <col style={{ width: 28 }} />
                        <col style={{ width: 78 }} />
                        <col />
                        <col style={{ width: 90 }} />
                        <col style={{ width: 46 }} />
                        <col style={{ width: 100 }} />
                        <col style={{ width: 120 }} />
                    </colgroup>
                    <thead>
                        <tr style={{ background: P.surfaceWarm }}>
                            {['#', 'Cat', 'Subject', 'Phone / ID', 'Age', 'Status', 'Owner'].map((h, i) => (
                                <th key={i} style={{
                                    textAlign: 'left', padding: '7px 10px',
                                    fontFamily: MONO, fontSize: 9, letterSpacing: '0.14em', color: P.ink3,
                                    textTransform: 'uppercase', fontWeight: 500,
                                    borderBottom: `1px solid ${P.hair}`,
                                }}>{h}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.length === 0 ? (
                            <tr>
                                <td colSpan={7} style={{ padding: '24px 16px', textAlign: 'center', color: P.ink3, fontSize: 12 }}>
                                    No cases found
                                </td>
                            </tr>
                        ) : filtered.map((g, i) => {
                            const sc = statusStyle(g.status);
                            return (
                                <tr
                                    key={g.id}
                                    style={{
                                        borderBottom: `1px solid ${P.hair}`,
                                        background: i % 2 === 1 ? 'rgba(0,0,0,0.012)' : 'transparent',
                                        cursor: 'pointer',
                                    }}
                                    onClick={() => onCaseClick(g.id)}
                                >
                                    <td style={{ padding: '7px 10px', fontFamily: MONO, fontSize: 10, color: P.ink3 }}>
                                        {(i + 1).toString().padStart(2, '0')}
                                    </td>
                                    <td style={{ padding: '7px 10px', fontSize: 11.5, color: P.ink2 }}>
                                        {g.category || '—'}
                                    </td>
                                    <td style={{ padding: '7px 10px', fontSize: 11.5, color: P.ink, lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {g.raw_message
                                            ? g.raw_message.slice(0, 80) + (g.raw_message.length > 80 ? '…' : '')
                                            : g.category || '—'}
                                    </td>
                                    <td style={{ padding: '7px 10px', fontFamily: MONO, fontSize: 10.5, color: P.ink2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {g.user_phone || g.user_id || '—'}
                                    </td>
                                    <td style={{ padding: '7px 10px', fontFamily: MONO, fontSize: 10.5, color: P.ink2 }}>
                                        {daysAgo(g.created_at)}
                                    </td>
                                    <td style={{ padding: '7px 10px' }}>
                                        <span style={{
                                            display: 'inline-flex', alignItems: 'center', gap: 5,
                                            padding: '1px 7px', background: sc.bg, color: sc.fg,
                                            fontSize: 10, fontWeight: 600,
                                        }}>
                                            <span style={{ width: 4, height: 4, background: sc.dot, borderRadius: '50%' }} />
                                            {statusLabel(g.status)}
                                        </span>
                                    </td>
                                    <td style={{ padding: '7px 10px', fontSize: 11, color: P.ink2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {g.assigned_to || <span style={{ color: P.ink3, fontStyle: 'italic' }}>unassigned</span>}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            <div style={{
                padding: '8px 16px', borderTop: `1px solid ${P.hair}`,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                background: P.surfaceWarm,
            }}>
                <span style={{ fontFamily: MONO, fontSize: 10, color: P.ink3, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                    Showing {filtered.length} case{filtered.length !== 1 ? 's' : ''}
                </span>
                <Link href="/dashboard/sansadx" style={{
                    padding: '4px 10px', background: 'transparent', border: `1px solid ${P.hair}`,
                    fontSize: 10.5, color: P.ink2, fontFamily: SANS, textDecoration: 'none',
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                }}>
                    Open full queue →
                </Link>
            </div>
        </section>
    );
}

// ─── Workload by Category ────────────────────────────────────────
function WorkloadCard({ summary }) {
    const cats = summary?.category_breakdown || {};
    const COLORS = [P.green, P.saffron, P.blue, P.greenDeep, '#A14B12', P.ink2];
    const entries = Object.entries(cats).sort((a, b) => b[1] - a[1]).slice(0, 6);
    const total = entries.reduce((s, [, v]) => s + v, 0) || 1;

    const segments = entries.map(([label, v], i) => ({ label, v, color: COLORS[i % COLORS.length] }));

    const topLabel = total > 999 ? `${(total / 1000).toFixed(1)}K` : String(total);

    return (
        <section style={{ background: P.surface, border: `1px solid ${P.hair}`, padding: 16, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 15, color: P.ink }}>
                    Workload by category
                </div>
                <span style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.12em', color: P.ink3, textTransform: 'uppercase' }}>
                    {total} cases
                </span>
            </div>
            {segments.length > 0 ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, flex: 1 }}>
                    <Donut segments={segments} size={96} thickness={16} label={topLabel} sub="total" />
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 5 }}>
                        {segments.map(s => {
                            const pct = ((s.v / total) * 100).toFixed(0);
                            return (
                                <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5 }}>
                                    <span style={{ width: 8, height: 8, background: s.color, flexShrink: 0 }} />
                                    <span style={{ flex: 1, color: P.ink, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.label}</span>
                                    <span style={{ fontFamily: MONO, color: P.ink2, fontSize: 10.5 }}>{s.v}</span>
                                    <span style={{ fontFamily: MONO, color: P.ink3, width: 28, textAlign: 'right', fontSize: 10.5 }}>{pct}%</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            ) : (
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <span style={{ color: P.ink3, fontSize: 12 }}>No data yet</span>
                </div>
            )}
        </section>
    );
}

// ─── Engagements / Schedule placeholder ────────────────────────
function EngagementsCard() {
    const today = new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' });
    // Placeholder items — would be replaced by a real calendar API
    const items = [
        { time: '09:00', dur: '60m', title: 'Constituency office hours', loc: 'Constituency Office', tag: 'Public' },
        { time: '11:30', dur: '30m', title: 'Team review · Grievance pipeline', loc: 'War room', tag: 'Internal' },
        { time: '14:00', dur: '90m', title: 'Site visit — Ward inspection', loc: 'Field', tag: 'Field' },
        { time: '16:30', dur: '45m', title: 'Press briefing', loc: 'Press cabin', tag: 'Media' },
    ];
    const tagColor = { Public: P.green, Internal: P.ink2, Field: P.saffron, Media: P.red, Govt: P.blue };

    return (
        <section style={{ background: P.surface, border: `1px solid ${P.hair}`, padding: 14, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
                <div>
                    <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 15, color: P.ink }}>
                        Today · Schedule
                    </div>
                    <div style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.12em', color: P.ink3, marginTop: 2, textTransform: 'uppercase' }}>
                        {today}
                    </div>
                </div>
            </div>

            <div style={{ flex: 1, overflow: 'hidden' }}>
                {items.map((e, i) => (
                    <div key={i} style={{
                        display: 'grid', gridTemplateColumns: '46px 1fr auto', gap: 12, padding: '7px 0',
                        borderBottom: i < items.length - 1 ? `1px solid ${P.hair}` : 'none',
                        alignItems: 'center',
                    }}>
                        <div style={{ fontFamily: MONO, fontSize: 11, color: P.ink2, fontWeight: 600 }}>{e.time}</div>
                        <div>
                            <div style={{ fontSize: 11.5, color: P.ink, fontWeight: 500, lineHeight: 1.3 }}>{e.title}</div>
                            <div style={{ fontSize: 10, color: P.ink3, marginTop: 1 }}>{e.loc} · {e.dur}</div>
                        </div>
                        <span style={{
                            fontFamily: MONO, fontSize: 9, letterSpacing: '0.1em',
                            color: tagColor[e.tag] || P.ink2, textTransform: 'uppercase', fontWeight: 700,
                        }}>{e.tag}</span>
                    </div>
                ))}
            </div>
        </section>
    );
}

// ─── Letters & Drafts ────────────────────────────────────────────
function LettersCard({ letters }) {
    function letterStatusStyle(s) {
        const norm = (s || '').toLowerCase();
        if (norm === 'new')       return { fg: P.saffron,  bg: P.saffronTint };
        if (norm === 'sent')      return { fg: P.greenInk, bg: P.greenTint };
        if (norm === 'draft')     return { fg: P.ink2,     bg: '#E8E2CC' };
        if (norm === 'signed')    return { fg: P.greenInk, bg: P.greenTint };
        if (norm === 'pending')   return { fg: P.saffron,  bg: P.saffronTint };
        return                           { fg: P.ink2,     bg: '#E8E2CC' };
    }

    return (
        <section style={{ background: P.surface, border: `1px solid ${P.hair}`, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px',
                borderBottom: `1px solid ${P.hair}`,
            }}>
                <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 15, color: P.ink }}>Letters & drafts</div>
                <span style={{ fontFamily: MONO, fontSize: 9.5, color: P.ink3, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                    {letters.length} in pipeline
                </span>
                <div style={{ flex: 1 }} />
                <Link href="/dashboard/drafter" style={{
                    padding: '4px 9px', background: P.green, color: '#F5EFE0', border: 'none',
                    fontSize: 10, letterSpacing: '0.08em', fontWeight: 600, textTransform: 'uppercase',
                    fontFamily: SANS, display: 'inline-flex', alignItems: 'center', gap: 4, textDecoration: 'none',
                }}>
                    + Draft
                </Link>
            </div>
            <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
                {letters.length === 0 ? (
                    <div style={{ padding: '24px 16px', textAlign: 'center', color: P.ink3, fontSize: 12 }}>
                        No letters in pipeline
                    </div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <tbody>
                            {letters.slice(0, 6).map((l, i) => {
                                const sc = letterStatusStyle(l.status);
                                return (
                                    <tr key={l.id || i} style={{ borderBottom: i < letters.length - 1 ? `1px solid ${P.hair}` : 'none' }}>
                                        <td style={{ padding: '8px 12px 8px 16px', fontFamily: MONO, fontSize: 10, color: P.ink2, verticalAlign: 'top', whiteSpace: 'nowrap' }}>
                                            #{(l.id || i + 1).toString().padStart(4, '0')}
                                        </td>
                                        <td style={{ padding: '8px 10px', verticalAlign: 'top' }}>
                                            <div style={{ fontSize: 11.5, color: P.ink, fontWeight: 500, lineHeight: 1.3 }}>
                                                {l.subject || l.content_preview || l.title || '—'}
                                            </div>
                                            <div style={{ fontSize: 10, color: P.ink3, marginTop: 2, fontStyle: 'italic' }}>
                                                {l.addressee || l.recipient || l.direction || '—'}
                                            </div>
                                        </td>
                                        <td style={{ padding: '8px 16px 8px 10px', textAlign: 'right', verticalAlign: 'top', whiteSpace: 'nowrap' }}>
                                            <span style={{
                                                padding: '1px 6px', background: sc.bg, color: sc.fg,
                                                fontSize: 9.5, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase',
                                            }}>{l.status || 'Draft'}</span>
                                            <div style={{ fontFamily: MONO, fontSize: 9.5, color: P.ink3, marginTop: 3 }}>
                                                {l.created_at ? new Date(l.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '—'}
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>
        </section>
    );
}

// ─── Press / Media monitoring ─────────────────────────────────────
function PressCard({ news }) {
    function toneBg(tone) {
        if (!tone) return { fg: P.ink2, bg: '#E8E2CC' };
        const t = tone.toLowerCase();
        if (t === 'positive') return { fg: P.greenInk, bg: P.greenTint };
        if (t === 'negative') return { fg: P.red,      bg: P.redTint };
        return                       { fg: P.ink2,     bg: '#E8E2CC' };
    }

    return (
        <section style={{ background: P.surface, border: `1px solid ${P.hair}`, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px',
                borderBottom: `1px solid ${P.hair}`,
            }}>
                <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 15, color: P.ink }}>Press monitoring</div>
                <span style={{ fontFamily: MONO, fontSize: 9.5, color: P.ink3, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                    {news.length} articles
                </span>
            </div>
            <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
                {news.length === 0 ? (
                    <div style={{ padding: '24px 16px', textAlign: 'center', color: P.ink3, fontSize: 12 }}>
                        No coverage fetched yet
                    </div>
                ) : news.slice(0, 6).map((p, i) => {
                    const t = toneBg(p.sentiment || p.tone);
                    return (
                        <div key={i} style={{
                            display: 'grid', gridTemplateColumns: '12px 1fr', gap: 10,
                            padding: '8px 16px',
                            borderBottom: i < Math.min(news.length, 6) - 1 ? `1px solid ${P.hair}` : 'none',
                            alignItems: 'flex-start',
                        }}>
                            <div style={{ width: 4, height: 32, background: t.fg, marginTop: 2, flexShrink: 0 }} />
                            <div>
                                <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', marginBottom: 2 }}>
                                    <div style={{ fontSize: 11.5, fontWeight: 600, color: P.ink, fontFamily: SERIF }}>
                                        {p.source || 'Unknown'}
                                    </div>
                                    <div style={{ fontFamily: MONO, fontSize: 9.5, color: P.ink3 }}>
                                        {p.published ? new Date(p.published).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''}
                                    </div>
                                </div>
                                <a
                                    href={p.link || p.url || '#'}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{ fontSize: 11, color: P.ink, lineHeight: 1.35, textDecoration: 'none' }}
                                >
                                    {p.title}
                                </a>
                            </div>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}

// ─── Activity feed ─────────────────────────────────────────────
function ActivityFeed({ cases, letters }) {
    // Build a synthetic activity feed from the most recently updated cases + letters
    const items = [
        ...cases.slice(0, 4).map(c => ({
            t: c.updated_at || c.created_at,
            who: c.assigned_to || 'System',
            act: (c.status || 'new').toLowerCase() === 'resolved' ? 'resolved' : 'updated',
            obj: `Case #${c.id} · ${c.category || 'Grievance'}`,
            tag: 'grievance',
        })),
        ...letters.slice(0, 3).map(l => ({
            t: l.updated_at || l.created_at,
            who: l.created_by || 'Staff',
            act: l.status === 'sent' ? 'sent' : 'drafted',
            obj: l.subject || `Letter #${l.id}`,
            tag: 'letter',
        })),
    ]
        .sort((a, b) => new Date(b.t) - new Date(a.t))
        .slice(0, 7);

    const tagColor = { grievance: P.saffron, letter: P.blue, press: P.red, engagement: P.green };

    function timeAgo(t) {
        if (!t) return '—';
        const d = new Date(t);
        if (isNaN(d)) return '—';
        const mins = Math.floor((Date.now() - d) / 60000);
        if (mins < 60) return `${mins}m ago`;
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return `${hrs}h ago`;
        return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
    }

    return (
        <section style={{ background: P.surface, border: `1px solid ${P.hair}`, padding: 14, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
                <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 15, color: P.ink }}>
                    Activity · recent
                </div>
                <span style={{ fontFamily: MONO, fontSize: 9.5, color: P.green, letterSpacing: '0.1em', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                    <span style={{ width: 6, height: 6, background: P.green, borderRadius: '50%' }} />
                    LIVE
                </span>
            </div>
            <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
                {items.length === 0 ? (
                    <div style={{ color: P.ink3, fontSize: 12, textAlign: 'center', paddingTop: 12 }}>
                        No recent activity
                    </div>
                ) : items.map((it, i) => (
                    <div key={i} style={{
                        display: 'grid', gridTemplateColumns: '48px 8px 1fr', gap: 8, padding: '6px 0',
                        borderBottom: i < items.length - 1 ? `1px solid ${P.hair}` : 'none',
                        alignItems: 'flex-start',
                    }}>
                        <div style={{ fontFamily: MONO, fontSize: 10, color: P.ink3, paddingTop: 2 }}>
                            {timeAgo(it.t)}
                        </div>
                        <div style={{ width: 6, height: 6, background: tagColor[it.tag] || P.ink2, marginTop: 6, borderRadius: '50%' }} />
                        <div style={{ fontSize: 11.5, color: P.ink, lineHeight: 1.4 }}>
                            <span style={{ fontWeight: 600 }}>{it.who}</span>
                            <span style={{ color: P.ink2 }}> {it.act} </span>
                            <span>{it.obj}</span>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}

// ─── Constituency Heat Map ───────────────────────────────────────
function ConstituencyMap({ summary, user }) {
    const redZones = summary?.red_zones || [];
    const cats = summary?.category_breakdown || {};
    const catEntries = Object.entries(cats).sort((a, b) => b[1] - a[1]).slice(0, 3);

    // Synthetic ward grid — 12 cells
    const maxLoad = Math.max(...redZones.map(z => z.count || 0), 1);
    function heat(n) {
        const t = (n || 0) / maxLoad;
        if (t > 0.75) return '#8B2E1F';
        if (t > 0.55) return P.saffron;
        if (t > 0.35) return '#D89E55';
        if (t > 0.18) return '#7DA08E';
        return P.greenTint;
    }

    const W = 340, H = 200;
    const outline = `M 35 110 C 25 70, 65 35, 110 32 C 155 28, 200 50, 235 38 C 280 28, 330 55, 345 100 C 360 145, 330 195, 280 205 C 230 215, 170 200, 115 210 C 60 220, 25 175, 35 110 Z`;
    const positions = [[70,80],[120,60],[170,95],[225,70],[280,95],[320,130],[85,145],[135,130],[195,150],[245,130],[290,165],[200,195]];

    // Map red zones to positional data (or show dots if no red zone data)
    const wardDots = redZones.length > 0
        ? redZones.slice(0, 12).map((z, i) => ({ ...z, pos: positions[i] || [170, 110] }))
        : positions.slice(0, 6).map((pos, i) => ({ pos, name: `Zone ${i + 1}`, count: 0 }));

    return (
        <section style={{ background: P.surface, border: `1px solid ${P.hair}`, padding: 16, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 8 }}>
                <div>
                    <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 15, color: P.ink }}>
                        Constituency map · {user?.constituency || '—'}
                    </div>
                    <div style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.12em', color: P.ink3, marginTop: 2, textTransform: 'uppercase' }}>
                        Grievance load · live
                    </div>
                </div>
                <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
                    {[P.greenTint, '#7DA08E', '#D89E55', P.saffron, '#8B2E1F'].map((c, i) => (
                        <span key={i} style={{ width: 12, height: 8, background: c, display: 'block' }} />
                    ))}
                </div>
            </div>

            <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
                <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" style={{ display: 'block' }}>
                    <path d={outline} fill={P.paperDeep} stroke={P.hairStrong} strokeWidth="1" strokeDasharray="2 3" />
                    <path d="M 40 195 C 90 175, 150 180, 200 170 S 320 160, 350 155"
                          stroke={P.blue} strokeWidth="2" fill="none" opacity="0.4" />
                    {wardDots.map((w, i) => {
                        const [cx, cy] = w.pos;
                        const r = 8 + (w.count ? (w.count / maxLoad) * 12 : 6);
                        return (
                            <g key={i}>
                                <circle cx={cx} cy={cy} r={r} fill={heat(w.count)} fillOpacity="0.85" stroke="#fff" strokeWidth="1.2" />
                                <text x={cx} y={cy + 3} fontFamily={SERIF} fontSize="9" fontWeight="600"
                                      fill={w.count > maxLoad * 0.35 ? '#F5EFE0' : P.ink} textAnchor="middle">
                                    {i + 1}
                                </text>
                            </g>
                        );
                    })}
                </svg>
            </div>

            {catEntries.length > 0 && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 10 }}>
                    {catEntries.map(([cat, count]) => (
                        <Link key={cat} href={`/dashboard/sansadx?category=${encodeURIComponent(cat)}`} style={{ textDecoration: 'none' }}>
                            <div style={{ padding: '6px 8px', background: P.paper, border: `1px solid ${P.hair}` }}>
                                <div style={{ fontFamily: MONO, fontSize: 9, color: P.ink3, letterSpacing: '0.08em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cat}</div>
                                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                                    <span style={{ fontFamily: SERIF, fontSize: 16, fontWeight: 600, color: P.ink }}>{count}</span>
                                    <span style={{ fontSize: 9.5, color: P.ink3 }}>cases</span>
                                </div>
                            </div>
                        </Link>
                    ))}
                </div>
            )}
        </section>
    );
}

// ─── Empty state ─────────────────────────────────────────────────
function EmptyState({ canUseSansadAI }) {
    return (
        <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            padding: '64px 24px', background: P.surface, border: `1px solid ${P.hair}`,
            textAlign: 'center', gap: 16,
        }}>
            <div style={{
                width: 64, height: 64, background: P.greenTint, display: 'flex',
                alignItems: 'center', justifyContent: 'center',
            }}>
                <span style={{ fontFamily: SERIF, fontSize: 32, color: P.green }}>क</span>
            </div>
            <div>
                <h2 style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 22, color: P.ink, marginBottom: 8 }}>
                    Welcome to Compass Needle
                </h2>
                <p style={{ fontSize: 14, color: P.ink2, maxWidth: 420, lineHeight: 1.6 }}>
                    Your constituency operations console is ready. Start by uploading a letter, logging a new case, or preparing your first response draft.
                </p>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center' }}>
                {[
                    { label: 'Upload a Letter', href: '/dashboard/letterbox' },
                    { label: 'Log a Case', href: '/dashboard/sansadx' },
                    ...(canUseSansadAI ? [{ label: 'Open Sansad AI', href: '/dashboard/sansadai' }] : []),
                    { label: 'Find a Scheme', href: '/dashboard/sansadai?tab=schemes' },
                ].map(a => (
                    <Link key={a.href} href={a.href} style={{
                        padding: '8px 16px', border: `1px solid ${P.hair}`,
                        background: P.paper, color: P.ink, fontSize: 12.5,
                        fontWeight: 500, textDecoration: 'none', transition: 'opacity 0.15s',
                    }}>
                        {a.label}
                    </Link>
                ))}
            </div>
        </div>
    );
}

// ─── Main Dashboard ────────────────────────────────────────────
export default function DashboardPage() {
    const { user } = useAuth();
    const router = useRouter();
    const canUseSansadAI = user?.role === 'mp' || user?.role === 'admin';

    const [summary, setSummary]   = useState(null);
    const [cases, setCases]       = useState([]);
    const [letters, setLetters]   = useState([]);
    const [news, setNews]         = useState([]);

    useEffect(() => {
        let cancelled = false;

        (async () => {
            const sum = await apiGet('/api/dashboard/summary').catch(() => ({ category_breakdown: {}, status_breakdown: {}, red_zones: [], critical_count: 0 }));
            if (!cancelled) setSummary(sum);
        })();

        (async () => {
            const res = await apiGet('/api/cases?page=1&limit=20').catch(() => ({ cases: [] }));
            if (!cancelled) setCases(res.cases || res.items || []);
        })();

        const timer = setTimeout(async () => {
            const [lb, nat] = await Promise.all([
                apiGet('/api/letterbox?direction=inbox&limit=10').catch(() => ({ items: [] })),
                apiGet('/api/news?news_type=national').catch(() => ({ articles: [] })),
            ]);
            if (!cancelled) {
                setLetters(lb.items || lb.letters || []);
                setNews(nat.articles || []);
            }
        }, 600);

        return () => { cancelled = true; clearTimeout(timer); };
    }, []);

    const statuses = summary?.status_breakdown || {};
    const totalCases = Object.values(statuses).reduce((a, b) => a + b, 0);
    const isEmpty = totalCases === 0 && cases.length === 0;

    const handleCaseClick = useCallback((id) => {
        router.push(`/dashboard/sansadx?case_id=${id}`);
    }, [router]);

    if (isEmpty && !summary) {
        return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
                <div style={{ fontFamily: MONO, fontSize: 11, letterSpacing: '0.14em', color: P.ink3, textTransform: 'uppercase' }}>
                    Loading…
                </div>
            </div>
        );
    }

    if (isEmpty) {
        return <EmptyState canUseSansadAI={canUseSansadAI} />;
    }

    return (
        <div style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1.55fr) minmax(0, 1fr)',
            gridTemplateRows: 'auto minmax(0,auto) minmax(0,auto)',
            gap: 14,
            fontFamily: SANS,
            fontSize: 12.5,
            color: P.ink,
        }}>
            {/* Row 1: KPI tiles — full width */}
            <div style={{ gridColumn: '1 / -1' }}>
                <KpiTiles summary={summary} cases={cases} />
            </div>

            {/* Row 2 left: Grievance table */}
            <GrievanceTable cases={cases} onCaseClick={handleCaseClick} />

            {/* Row 2 right: Workload + Engagements */}
            <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', gap: 14 }}>
                <WorkloadCard summary={summary} />
                <EngagementsCard />
            </div>

            {/* Row 3 left: Letters + Press */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <LettersCard letters={letters} />
                <PressCard news={news} />
            </div>

            {/* Row 3 right: Map + Activity */}
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 14 }}>
                <ConstituencyMap summary={summary} user={user} />
                <ActivityFeed cases={cases} letters={letters} />
            </div>
        </div>
    );
}
