'use client';

import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { PERIOD_PRESETS, fmtDate, periodKey, toPeriod } from '@/lib/partnerFormat';

/* ─────────── Icons (stroke, 20-unit grid) ─────────── */
const PATHS = {
    home: <><path d="M3 10.5 10 4l7 6.5V17H3z" /><path d="M8 17v-4h4v4" /></>,
    clients: <><rect x="3" y="4" width="14" height="12" rx="1.5" /><path d="M3 8h14M7 8v8" /></>,
    report: <><path d="M5 2.5h7l3 3V17.5H5z" /><path d="M12 2.5v3h3M8 10h4M8 13h4" /></>,
    settings: <><circle cx="10" cy="10" r="2.6" /><path d="M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.7 4.7l1.4 1.4M13.9 13.9l1.4 1.4M4.7 15.3l1.4-1.4M13.9 6.1l1.4-1.4" /></>,
    search: <><circle cx="9" cy="9" r="5.5" /><path d="m13 13 4 4" /></>,
    chev: <path d="m8 5 5 5-5 5" />,
    down: <path d="m5 8 5 5 5-5" />,
    menu: <path d="M3 6h14M3 10h14M3 14h14" />,
    download: <path d="M10 3v10M6 9l4 4 4-4M4 16.5h12" />,
    external: <path d="M11 3.5h5.5V9M16.5 3.5 9 11M14 12v4.5H3.5V6H8" />,
    swap: <path d="M4 7h12l-3-3M16 13H4l3 3" />,
    out: <path d="M8 4H4v12h4M12 6l4 4-4 4M16 10H8" />,
    clock: <><circle cx="10" cy="10" r="7.5" /><path d="M10 6v4l2.5 2" /></>,
    retry: <path d="M15.5 8A6 6 0 1 0 16 12M16 4v4h-4" />,
    alert: <><circle cx="10" cy="10" r="7.5" /><path d="M10 6v4.5M10 13.5v.1" /></>,
};
export function Icon({ name, size = 18 }) {
    return (
        <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6"
            strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{PATHS[name]}</svg>
    );
}

/* ─────────── Chrome context (breadcrumb set by pages, read by the shell) ─────────── */
export const PartnerChromeContext = createContext(null);
/** Pages call this with their breadcrumb trail. Outside the shell (e.g. in tests) it is a no-op. */
export function useCrumbs(crumbs) {
    const ctx = useContext(PartnerChromeContext);
    const key = JSON.stringify(crumbs);
    useEffect(() => {
        if (ctx) ctx.setCrumbs(JSON.parse(key));
    }, [ctx, key]);
}

export function useNarrow(breakpoint = 760) {
    const [narrow, setNarrow] = useState(false);
    useEffect(() => {
        if (typeof window === 'undefined' || !window.matchMedia) return undefined;
        const mq = window.matchMedia(`(max-width: ${breakpoint}px)`);
        const update = () => setNarrow(mq.matches);
        update();
        mq.addEventListener?.('change', update);
        return () => mq.removeEventListener?.('change', update);
    }, [breakpoint]);
    return narrow;
}

/* ─────────── Small building blocks ─────────── */
export function Badge({ tone = 'neutral', children }) {
    return <span className={`pd-badge pd-b-${tone}`}>{children}</span>;
}

const todayIso = () => new Date().toISOString().slice(0, 10);

/** Presets (7 / 30 / 90 days, 1 year, All time) plus a custom inclusive date range. */
export function PeriodSelect({ period, onChange, days }) {
    const current = toPeriod(period ?? days);
    const key = periodKey(current);
    const [open, setOpen] = useState(false);
    const [from, setFrom] = useState(current.kind === 'custom' ? current.from : '');
    const [to, setTo] = useState(current.kind === 'custom' ? current.to : todayIso());
    const [error, setError] = useState('');
    const ref = useRef(null);

    useEffect(() => {
        if (!open) return undefined;
        const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
        const esc = (e) => { if (e.key === 'Escape') setOpen(false); };
        document.addEventListener('mousedown', close);
        document.addEventListener('keydown', esc);
        return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc); };
    }, [open]);

    function apply(e) {
        e.preventDefault();
        if (!from || !to) return setError('Choose both dates.');
        if (from > to) return setError('The start date must be on or before the end date.');
        if (to > todayIso()) return setError('The end date cannot be in the future.');
        setError('');
        setOpen(false);
        onChange({ kind: 'custom', from, to });
    }

    return (
        <div className="pd-dd" ref={ref} style={{ display: 'inline-flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <div role="group" aria-label="Reporting period" className="pd-seg">
                {PERIOD_PRESETS.map((p) => (
                    <button key={p.key} type="button" aria-pressed={key === periodKey(p.period)} onClick={() => onChange(p.period)}>{p.label}</button>
                ))}
                <button type="button" aria-pressed={current.kind === 'custom'} aria-expanded={open} aria-haspopup="dialog"
                    onClick={() => setOpen((o) => !o)}>
                    {current.kind === 'custom' ? `${fmtDate(current.from)} – ${fmtDate(current.to)}` : 'Custom'}
                </button>
            </div>
            {open ? (
                <form className="pd-pop" role="dialog" aria-label="Custom date range" onSubmit={apply} style={{ padding: 14, width: 280 }}>
                    <div style={{ display: 'grid', gap: 10 }}>
                        <label className="pd-label" style={{ margin: 0 }}>From
                            <input className="pd-input" type="date" value={from} max={to || todayIso()} onChange={(e) => setFrom(e.target.value)} style={{ marginTop: 4 }} />
                        </label>
                        <label className="pd-label" style={{ margin: 0 }}>To
                            <input className="pd-input" type="date" value={to} min={from || undefined} max={todayIso()} onChange={(e) => setTo(e.target.value)} style={{ marginTop: 4 }} />
                        </label>
                        {error ? <div role="alert" className="pd-csub" style={{ color: 'var(--crit)' }}>{error}</div> : null}
                        <button type="submit" className="pd-btn primary" style={{ justifyContent: 'center' }}>Apply range</button>
                    </div>
                </form>
            ) : null}
        </div>
    );
}

/** Headline metrics in one hairline-divided panel. items: [{ label, value, unit, foot, tone }] */
export function Kpis({ items, label }) {
    return (
        <section className="pd-panel pd-kpis" style={{ '--n': items.length }} aria-label={label}>
            {items.map((k) => (
                <div className="pd-kpi" key={k.label}>
                    <div className="pd-kpi-label">{k.label}</div>
                    <div className="pd-kpi-val" style={k.tone === 'crit' ? { color: 'var(--crit)' } : undefined}>
                        {k.value}{k.unit ? <small>{k.unit}</small> : null}
                    </div>
                    <div className="pd-kpi-foot">{k.foot || null}</div>
                </div>
            ))}
        </section>
    );
}

export function ErrorState({ title, message, onRetry }) {
    return (
        <div role="alert" className="pd-alert">
            <span style={{ display: 'inline-flex', gap: 8, alignItems: 'flex-start' }}>
                <Icon name="alert" size={16} /> <span>{title} {message}</span>
            </span>
            {onRetry ? (
                <button type="button" className="pd-btn sm" onClick={onRetry}><Icon name="retry" size={15} /> Retry</button>
            ) : null}
        </div>
    );
}

export function Skel({ h = 96, w = '100%', style }) {
    return <div className="pd-skel" style={{ height: h, width: w, ...style }} />;
}

/** Ranked horizontal bars. items: [{ key, label, count }] — share is of `total` when given. */
export function RankedBars({ items, total, empty }) {
    if (!items.length) return <p className="muted" style={{ fontSize: 13, margin: 0 }}>{empty}</p>;
    const max = Math.max(1, ...items.map((i) => i.count));
    return (
        <ul className="pd-ranked">
            {items.map((i) => (
                <li key={i.key}>
                    <span className="lab" title={i.label}>{i.label}</span>
                    <span className="bar" aria-hidden="true"><b style={{ width: `${(i.count / max) * 100}%` }} /></span>
                    <span className="val num">{i.count}{total ? <span>{Math.round((i.count / total) * 100)}%</span> : null}</span>
                </li>
            ))}
        </ul>
    );
}

export function SectionHead({ id, title, sub, right }) {
    return (
        <div className="pd-sechead">
            <div>
                <h2 className="pd-sec" id={id}>{title}</h2>
                {sub ? <div className="pd-secsub">{sub}</div> : null}
            </div>
            {right || null}
        </div>
    );
}
