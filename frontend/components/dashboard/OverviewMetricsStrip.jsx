'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { apiGet } from '@/lib/api';
import { gen2, gen2Fonts } from '@/lib/briefcase-tokens';

// Staff Overview top strip: six period numbers, each opening the list behind it.
// Definitions match the partner briefing (modules/overview_metrics.py).
export const METRICS = [
    { key: 'complaints', label: 'Complaints', goodWhen: null, unit: 'complaints' },
    { key: 'filed', label: 'Filed with Government', goodWhen: 'up', unit: 'complaints filed' },
    { key: 'resolved', label: 'Resolved by Government', goodWhen: 'up', unit: 'complaints resolved' },
    { key: 'other_actions', label: 'Other Actions', goodWhen: 'up', unit: 'complaints acted on' },
    { key: 'pending', label: 'Pending', goodWhen: 'down', unit: 'complaints pending' },
    { key: 'new_contacts', label: 'New Contacts', goodWhen: 'up', unit: 'new people' },
];

export const PERIODS = [
    { key: '7', label: '7 days', query: 'days=7', phrase: 'the last 7 days' },
    { key: '30', label: '30 days', query: 'days=30', phrase: 'the last 30 days' },
    { key: '90', label: '90 days', query: 'days=90', phrase: 'the last 90 days' },
    { key: 'all', label: 'All time', query: 'range=all', phrase: 'all time' },
];

const HINT = {
    complaints: 'Grievances received in the period. Spam and abuse are not counted.',
    filed: 'Received in the period and filed with a government portal or department.',
    resolved: 'Received in the period, filed, and reported resolved by government.',
    other_actions: 'Handled without a government filing: a letter, a referral, a local fix or information given.',
    pending: 'Received in the period with no action yet.',
    new_contacts: 'People who reached the office for the first time in the period.',
};

export function changeText(value, previous, goodWhen) {
    if (previous === null || previous === undefined) return null;
    if (value === previous) return { text: 'no change', tone: 'flat' };
    if (!previous) return { text: 'new', tone: 'flat' };
    const pct = Math.round(((value - previous) / previous) * 100);
    const up = pct > 0;
    const tone = goodWhen ? (up === (goodWhen === 'up') ? 'good' : 'bad') : 'flat';
    return { text: `${up ? '↑' : '↓'} ${Math.abs(pct)}%`, tone };
}

function ageText(days) {
    if (days === null || days === undefined) return '';
    return days === 0 ? 'today' : `${days}d`;
}

function CaseRow({ c, onOpenCase }) {
    return (
        <button type="button" className="om-case" onClick={() => onOpenCase(c.id)}>
            <span className="om-ref">{c.case_ref}</span>
            <span className="om-msg">{c.preview || '—'}</span>
            <span className="om-meta">{[c.category, c.locality].filter(Boolean).join(' · ')}</span>
            <span className="om-age">{ageText(c.age_days)}</span>
        </button>
    );
}

function MetricDrawer({ metric, period, onClose, onOpenCase }) {
    const [state, setState] = useState({ status: 'loading', data: null });
    const closeRef = useRef(null);

    useEffect(() => {
        let cancelled = false;
        setState({ status: 'loading', data: null });
        apiGet(`/api/dashboard/overview/metrics/${metric.key}?${period.query}&limit=100`)
            .then((data) => { if (!cancelled) setState({ status: 'ready', data }); })
            .catch(() => { if (!cancelled) setState({ status: 'error', data: null }); });
        return () => { cancelled = true; };
    }, [metric.key, period.query]);

    useEffect(() => {
        closeRef.current?.focus();
        const onKey = (e) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [onClose]);

    const d = state.data;
    const shown = d ? (d.cases || d.contacts || []).length : 0;
    return (
        <div className="om-overlay" onClick={onClose} role="presentation">
            <aside className="om-drawer" role="dialog" aria-modal="true" aria-label={`${metric.label}, ${period.phrase}`}
                onClick={(e) => e.stopPropagation()}>
                <header className="om-dhead">
                    <div>
                        <p className="om-kicker">{period.phrase}</p>
                        <h2>{metric.label}{d ? ` · ${d.total}` : ''}</h2>
                        <p className="om-hint">{HINT[metric.key]}</p>
                    </div>
                    <button type="button" ref={closeRef} className="om-close" onClick={onClose} aria-label="Close">×</button>
                </header>
                <div className="om-body">
                    {state.status === 'loading' ? <p className="om-empty">Loading…</p> : null}
                    {state.status === 'error' ? <p className="om-empty" role="alert">This list could not be loaded. Close and try again.</p> : null}
                    {state.status === 'ready' && shown === 0 ? <p className="om-empty">Nothing here for this period.</p> : null}
                    {d && d.cases ? d.cases.map((c) => <CaseRow key={c.id} c={c} onOpenCase={onOpenCase} />) : null}
                    {d && d.contacts ? d.contacts.map((p, i) => (
                        <section className="om-person" key={`${p.label}-${i}`}>
                            <div className="om-phead">
                                <strong>{p.label}</strong>
                                <span>{p.case_count} {p.case_count === 1 ? 'complaint' : 'complaints'}
                                    {p.first_contact ? ` · first contact ${new Date(p.first_contact).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}` : ''}</span>
                            </div>
                            {p.cases.map((c) => <CaseRow key={c.id} c={c} onOpenCase={onOpenCase} />)}
                        </section>
                    )) : null}
                    {d && d.total > shown ? <p className="om-empty">Showing the latest {shown} of {d.total}.</p> : null}
                </div>
            </aside>
        </div>
    );
}

export default function OverviewMetricsStrip({ onOpenCase }) {
    const [periodKey, setPeriodKey] = useState('30');
    const [state, setState] = useState({ status: 'loading', metrics: {} });
    const [open, setOpen] = useState(null);
    const period = PERIODS.find((p) => p.key === periodKey) || PERIODS[1];

    useEffect(() => {
        let cancelled = false;
        setState((s) => ({ ...s, status: 'loading' }));
        apiGet(`/api/dashboard/overview/metrics?${period.query}`)
            .then((res) => {
                if (cancelled) return;
                const metrics = {};
                (res?.metrics || []).forEach((m) => { metrics[m.key] = m; });
                setState({ status: 'ready', metrics });
            })
            .catch(() => { if (!cancelled) setState({ status: 'error', metrics: {} }); });
        return () => { cancelled = true; };
    }, [period.query]);

    const close = useCallback(() => setOpen(null), []);
    const openCase = (id) => { setOpen(null); onOpenCase(id); };

    return (
        <section className="om" aria-label="Key numbers">
            <div className="om-top">
                <span className="om-period-label">Grievances received in {period.phrase}</span>
                <div className="om-seg" role="group" aria-label="Period">
                    {PERIODS.map((p) => (
                        <button key={p.key} type="button" aria-pressed={p.key === periodKey} onClick={() => setPeriodKey(p.key)}>{p.label}</button>
                    ))}
                </div>
            </div>
            {state.status === 'error' ? <p className="om-error" role="alert">The numbers could not be loaded right now.</p> : null}
            <div className="om-strip">
                {METRICS.map((m) => {
                    const v = state.metrics[m.key];
                    const chg = v ? changeText(v.value, v.previous, m.goodWhen) : null;
                    return (
                        <button type="button" key={m.key} className={`om-tile${m.key === 'pending' && v?.value ? ' warn' : ''}`}
                            onClick={() => setOpen(m)} disabled={!v} aria-label={v ? `${m.label}: ${v.value}. Show the list` : m.label}>
                            <span className="om-label">{m.label}</span>
                            <span className="om-value">{v ? v.value.toLocaleString('en-IN') : '—'}</span>
                            <span className="om-chg">
                                {chg ? <span className={chg.tone}>{chg.text}</span> : null}
                                {v && v.previous !== null && v.previous !== undefined ? <span className="om-vs">vs {v.previous}</span> : null}
                            </span>
                        </button>
                    );
                })}
            </div>
            {open ? <MetricDrawer metric={open} period={period} onClose={close} onOpenCase={openCase} /> : null}
            <style>{`
                .om { margin-bottom: 13px; }
                .om-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
                .om-period-label { font-family: ${gen2Fonts.mono}; font-size: 10.5px; letter-spacing: .12em; text-transform: uppercase; color: ${gen2.muted}; }
                .om-seg { display: inline-flex; border: 1px solid ${gen2.hairStrong}; background: ${gen2.surface}; }
                .om-seg button { border: 0; background: none; padding: 5px 11px; font: 600 12px ${gen2Fonts.sans}; color: ${gen2.muted}; cursor: pointer; }
                .om-seg button[aria-pressed="true"] { background: ${gen2.ink}; color: #fff; }
                .om-strip { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); background: ${gen2.surface}; border: 1px solid ${gen2.hair}; }
                .om-tile { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; padding: 12px 14px; border: 0; border-right: 1px solid ${gen2.hair}; background: none; text-align: left; cursor: pointer; font: inherit; color: inherit; min-width: 0; }
                .om-tile:last-child { border-right: 0; }
                .om-tile:hover:not(:disabled) { background: ${gen2.rowHover}; }
                .om-tile:focus-visible { outline: 2px solid ${gen2.green}; outline-offset: -2px; }
                .om-tile:disabled { cursor: default; }
                .om-label { font-family: ${gen2Fonts.mono}; font-size: 10px; letter-spacing: .1em; text-transform: uppercase; color: ${gen2.muted}; line-height: 1.3; min-height: 26px; }
                .om-value { font-family: ${gen2Fonts.serif}; font-size: 30px; font-weight: 600; line-height: 1; color: ${gen2.ink}; font-variant-numeric: tabular-nums; }
                .om-tile.warn .om-value { color: ${gen2.err}; }
                .om-chg { display: flex; gap: 6px; font-size: 11.5px; min-height: 16px; }
                .om-chg .good { color: ${gen2.green}; font-weight: 600; }
                .om-chg .bad { color: ${gen2.err}; font-weight: 600; }
                .om-chg .flat, .om-vs { color: ${gen2.muted}; }
                .om-error { color: ${gen2.err}; font-size: 12px; margin: 0 0 6px; }
                .om-overlay { position: fixed; inset: 0; background: rgba(33, 31, 25, .28); z-index: 80; display: flex; justify-content: flex-end; }
                .om-drawer { width: min(560px, 100%); height: 100%; background: ${gen2.surface}; border-left: 1px solid ${gen2.hairStrong}; display: flex; flex-direction: column; box-shadow: -8px 0 28px rgba(0,0,0,.12); }
                .om-dhead { display: flex; justify-content: space-between; gap: 12px; padding: 18px 20px 14px; border-bottom: 1px solid ${gen2.hair}; }
                .om-dhead h2 { font-family: ${gen2Fonts.serif}; font-size: 24px; margin: 2px 0 4px; color: ${gen2.ink}; }
                .om-kicker { margin: 0; font-family: ${gen2Fonts.mono}; font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: ${gen2.muted}; }
                .om-hint { margin: 0; font-size: 12.5px; color: ${gen2.muted}; }
                .om-close { border: 1px solid ${gen2.hairStrong}; background: none; width: 32px; height: 32px; font-size: 20px; line-height: 1; cursor: pointer; color: ${gen2.ink}; flex: none; }
                .om-body { overflow-y: auto; padding: 6px 0 20px; }
                .om-empty { padding: 14px 20px; color: ${gen2.muted}; font-size: 13px; margin: 0; }
                .om-case { display: grid; grid-template-columns: 70px 1fr 40px; grid-template-areas: "ref msg age" "ref meta age"; column-gap: 10px; row-gap: 2px; width: 100%; padding: 10px 20px; border: 0; border-bottom: 1px solid ${gen2.hair}; background: none; text-align: left; cursor: pointer; font: inherit; color: inherit; }
                .om-case:hover { background: ${gen2.rowHover}; }
                .om-case:focus-visible { outline: 2px solid ${gen2.green}; outline-offset: -2px; }
                .om-ref { grid-area: ref; font-family: ${gen2Fonts.mono}; font-size: 11.5px; color: ${gen2.muted}; }
                .om-msg { grid-area: msg; font-weight: 600; font-size: 13.5px; color: ${gen2.ink}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
                .om-meta { grid-area: meta; font-size: 12px; color: ${gen2.muted}; }
                .om-age { grid-area: age; font-family: ${gen2Fonts.mono}; font-size: 11.5px; color: ${gen2.muted}; text-align: right; }
                .om-person { border-bottom: 1px solid ${gen2.hairStrong}; }
                .om-phead { display: flex; justify-content: space-between; gap: 10px; padding: 12px 20px 6px; background: ${gen2.activeTint}; }
                .om-phead strong { font-size: 13.5px; color: ${gen2.ink}; }
                .om-phead span { font-size: 12px; color: ${gen2.muted}; }
                @media (max-width: 1100px) {
                    .om-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }
                    .om-tile:nth-child(3) { border-right: 0; }
                    .om-tile:nth-child(n+4) { border-top: 1px solid ${gen2.hair}; }
                }
                @media (max-width: 640px) {
                    .om-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                    .om-tile:nth-child(3) { border-right: 1px solid ${gen2.hair}; }
                    .om-tile:nth-child(even) { border-right: 0; }
                    .om-tile:nth-child(n+3) { border-top: 1px solid ${gen2.hair}; }
                    .om-value { font-size: 26px; }
                    .om-seg { width: 100%; }
                    .om-seg button { flex: 1; padding: 6px 4px; }
                    .om-drawer { width: 100%; }
                }
            `}</style>
        </section>
    );
}
