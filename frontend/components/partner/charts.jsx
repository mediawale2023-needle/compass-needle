'use client';

import { useState } from 'react';
import { useNarrow } from './ui';

/* Small SVG chart kit: labelled axes, gridlines, legend outside, hover tooltip, and an accessible summary. */

function niceMax(v) {
    const p = 10 ** Math.floor(Math.log10(v || 1));
    for (const m of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
    return 10 * p;
}
const fmtInt = (v) => Math.round(v).toLocaleString('en-IN');

function useTip() {
    const [tip, setTip] = useState(null);
    const show = (text) => (e) => setTip({ text, x: e.clientX, y: e.clientY });
    const hide = () => setTip(null);
    const node = tip ? (
        <div className="pd-tip" style={{ left: Math.min(tip.x + 14, (typeof window !== 'undefined' ? window.innerWidth : 9999) - 220), top: tip.y + 16 }}>{tip.text}</div>
    ) : null;
    return { show, hide, node };
}

function Frame({ W, h, P, max, yFmt, labels, xAt, ariaLabel, children }) {
    const ih = h - P.t - P.b;
    const y = (v) => P.t + ih - (v / max) * ih;
    const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max);
    // Keep x labels from colliding: about 70px per label.
    const step = Math.max(1, Math.ceil(labels.length / Math.max(2, Math.floor((W - P.l - P.r) / 70))));
    return (
        <svg className="pd-chart" viewBox={`0 0 ${W} ${h}`} role="img" aria-label={ariaLabel}>
            <g className="grid">
                {ticks.map((t) => (
                    <g key={t}>
                        <line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} />
                        <text x={P.l - 8} y={y(t) + 4} textAnchor="end">{yFmt(t)}</text>
                    </g>
                ))}
            </g>
            {labels.map((l, i) => (i % step === 0 ? (
                <text key={l + i} x={xAt(i)} y={h - 8} textAnchor={i === 0 && xAt(0) - P.l < 30 ? 'start' : i === labels.length - 1 && W - P.r - xAt(i) < 30 ? 'end' : 'middle'}>{l}</text>
            ) : null))}
            {children(y)}
        </svg>
    );
}

export function BarChart({ labels, series, height = 260, width = 600, ariaLabel, yFmt = fmtInt }) {
    const narrow = useNarrow();
    const W = narrow ? 360 : width;
    const P = { l: 44, r: 12, t: 18, b: 30 };
    const iw = W - P.l - P.r;
    const ih = height - P.t - P.b;
    const max = niceMax(Math.max(1, ...series.flatMap((s) => s.values)) * 1.1);
    const band = iw / Math.max(1, labels.length);
    const gap = band * 0.28;
    const bw = (band - gap) / series.length;
    const { show, hide, node } = useTip();
    const showValues = labels.length <= 8 && !narrow;
    return (
        <>
            <Frame W={W} h={height} P={P} max={max} yFmt={yFmt} labels={labels} ariaLabel={ariaLabel}
                xAt={(i) => P.l + i * band + band / 2}>
                {(y) => (
                    <>
                        {labels.map((l, i) => {
                            const x0 = P.l + i * band + gap / 2;
                            const tipText = `${l}\n${series.map((s) => `${s.name}: ${fmtInt(s.values[i])}`).join('\n')}`;
                            return (
                                <g key={l + i}>
                                    {series.map((s, j) => {
                                        const v = s.values[i] || 0;
                                        const bx = x0 + j * bw;
                                        return (
                                            <g key={s.name}>
                                                <rect x={bx} y={y(v)} width={Math.max(1, bw - 1.5)} height={P.t + ih - y(v)} fill={s.color} rx="1" />
                                                {showValues ? <text x={bx + bw / 2} y={y(v) - 5} textAnchor="middle" style={{ fill: 'var(--ink-2)', fontSize: 10.5 }}>{fmtInt(v)}</text> : null}
                                            </g>
                                        );
                                    })}
                                    <rect className="hit" x={P.l + i * band} y={P.t} width={band} height={ih}
                                        onMouseMove={show(tipText)} onMouseLeave={hide}><title>{tipText}</title></rect>
                                </g>
                            );
                        })}
                        <line className="axis" x1={P.l} x2={W - P.r} y1={P.t + ih} y2={P.t + ih} />
                    </>
                )}
            </Frame>
            {node}
        </>
    );
}

export function LineChart({ labels, series, height = 260, width = 760, ariaLabel, yFmt = fmtInt, yMax, tipFmt }) {
    const narrow = useNarrow();
    const W = narrow ? 360 : width;
    const P = { l: 44, r: 16, t: 14, b: 30 };
    const iw = W - P.l - P.r;
    const ih = height - P.t - P.b;
    const values = series.flatMap((s) => s.values.filter((v) => v !== null && v !== undefined));
    const max = yMax || niceMax(Math.max(1, ...values) * 1.08);
    const x = (i) => P.l + (labels.length <= 1 ? iw / 2 : (i * iw) / (labels.length - 1));
    const band = iw / Math.max(1, labels.length - 1);
    const fmtTip = tipFmt || yFmt;
    const { show, hide, node } = useTip();
    return (
        <>
            <Frame W={W} h={height} P={P} max={max} yFmt={yFmt} labels={labels} ariaLabel={ariaLabel} xAt={x}>
                {(y) => (
                    <>
                        {series.map((s) => {
                            let d = '';
                            s.values.forEach((v, i) => {
                                if (v === null || v === undefined) return;
                                d += `${d ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
                            });
                            const lastIdx = s.values.map((v) => v !== null && v !== undefined).lastIndexOf(true);
                            return (
                                <g key={s.name}>
                                    <path d={d} fill="none" stroke={s.color} strokeWidth={s.width || 2.2}
                                        strokeDasharray={s.dash ? '4 4' : undefined} strokeLinejoin="round" strokeLinecap="round" />
                                    {lastIdx >= 0 ? <circle cx={x(lastIdx)} cy={y(s.values[lastIdx])} r="3.5" fill={s.color} /> : null}
                                </g>
                            );
                        })}
                        {labels.map((l, i) => {
                            const tipText = `${l}\n${series.map((s) => `${s.name}: ${s.values[i] === null || s.values[i] === undefined ? '—' : fmtTip(s.values[i])}`).join('\n')}`;
                            return (
                                <rect key={l + i} className="hit" x={x(i) - band / 2} y={P.t} width={band} height={ih}
                                    onMouseMove={show(tipText)} onMouseLeave={hide}><title>{tipText}</title></rect>
                            );
                        })}
                    </>
                )}
            </Frame>
            {node}
        </>
    );
}

export function Legend({ items }) {
    return (
        <div className="pd-legend">
            {items.map((i) => (
                <span key={i.label}><i className={i.line ? 'line' : ''} style={{ background: i.color }} />{i.label}</span>
            ))}
        </div>
    );
}

/** Axis label for one trend bucket: a day or week shows its end date, longer buckets their month or year. */
export function bucketLabel(bucket, bucketDays) {
    const d = new Date(`${bucket.period_end}T00:00:00Z`);
    if (Number.isNaN(d.getTime())) return bucket.period_end;
    if (bucketDays >= 365) return String(d.getUTCFullYear());
    if (bucketDays >= 30) return d.toLocaleDateString('en-GB', { month: 'short', year: '2-digit', timeZone: 'UTC' });
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
}

/** "2026-11-16" -> "16 Nov" */
export function weekLabel(iso) {
    const d = new Date(`${iso}T00:00:00`);
    if (Number.isNaN(d.getTime())) return iso;
    return `${d.getDate()} ${d.toLocaleString('en-GB', { month: 'short' })}`;
}
