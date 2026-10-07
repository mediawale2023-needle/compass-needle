'use client';

/**
 * Lightweight SVG charts. They render only the data they are given; with no
 * data they render nothing (callers show an Unavailable/Empty state).
 */

function scale(values, height, pad) {
    const nums = values.map(Number).filter((v) => Number.isFinite(v));
    const min = Math.min(...nums);
    const max = Math.max(...nums);
    const span = max - min || 1;
    return (value) => pad + (height - pad * 2) * (1 - (Number(value) - min) / span);
}

export function Sparkline({ values = [], tone = 'forest', label, width = 120, height = 36, area = false }) {
    if (values.length < 2) return null;
    const y = scale(values, height, 3);
    const step = width / (values.length - 1);
    const points = values.map((value, index) => `${(index * step).toFixed(1)},${y(value).toFixed(1)}`);
    const line = `M${points.join(' L')}`;
    return (
        <svg className="nx-spark" data-tone={tone} width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
            {area && <path d={`${line} L${width},${height} L0,${height} Z`} className="nx-spark-area" />}
            <path d={line} className="nx-spark-line" />
        </svg>
    );
}

/**
 * Multi-series line chart with gridlines and x labels.
 * series = [{ label, values, tone }]; labels = x-axis labels (same length).
 */
export function LineChart({ series = [], labels = [], height = 200, ariaLabel, yTicks = 4, zeroBased = false, viewWidth = 640 }) {
    const all = series.flatMap((s) => s.values).map(Number).filter(Number.isFinite);
    if (!all.length || labels.length < 2) return null;
    // viewWidth ≈ the rendered width keeps axis text at its intended size.
    const width = viewWidth;
    const left = 36;
    const bottom = 22;
    const top = 10;
    const plotH = height - bottom - top;
    // Lines read movement, so the axis fits the data unless zeroBased is set;
    // tick labels always state the real range.
    const lo = Math.min(...all);
    const hi = Math.max(...all);
    const pad = Math.max(1, (hi - lo) * 0.15);
    const step = Math.pow(10, Math.max(0, Math.floor(Math.log10(Math.max(hi - lo, 1)))));
    const min = zeroBased ? Math.min(0, lo) : Math.max(0, Math.floor((lo - pad) / step) * step);
    const max = Math.ceil((hi + pad) / step) * step || 1;
    const span = max - min || 1;
    const x = (i) => left + ((width - left - 8) * i) / (labels.length - 1);
    const y = (v) => top + plotH * (1 - (Number(v) - min) / span);
    const ticks = Array.from({ length: yTicks + 1 }, (_, i) => min + (span * i) / yTicks);
    const labelEvery = Math.ceil(labels.length / 6);
    return (
        <svg className="nx-linechart" viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label={ariaLabel}>
            {ticks.map((tick) => (
                <g key={tick}>
                    <line x1={left} x2={width - 8} y1={y(tick)} y2={y(tick)} className="nx-grid" />
                    <text x={left - 8} y={y(tick) + 4} textAnchor="end" className="nx-axis">{Math.round(tick)}</text>
                </g>
            ))}
            {labels.map((label, i) => (i % labelEvery === 0 || i === labels.length - 1) && (
                <text key={label} x={x(i)} y={height - 4} textAnchor={i === labels.length - 1 ? 'end' : i === 0 ? 'start' : 'middle'} className="nx-axis">{label}</text>
            ))}
            {series.map((s) => (
                <path key={s.label} d={s.values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')} className="nx-series" data-tone={s.tone || 'forest'} />
            ))}
        </svg>
    );
}

/** Horizontal labelled bars. items = [{ label, value, tone }]. */
export function BarList({ items = [], max }) {
    const top = max ?? Math.max(1, ...items.map((item) => Number(item.value) || 0));
    return (
        <ul className="nx-barlist">
            {items.map((item) => (
                <li key={item.label}>
                    <div className="nx-barlist-row"><span>{item.label}</span><strong>{item.value}</strong></div>
                    <div className="nx-progress"><span data-tone={item.tone || 'forest'} style={{ width: `${(Number(item.value) / top) * 100}%` }} /></div>
                </li>
            ))}
        </ul>
    );
}

export function ChartLegend({ items = [] }) {
    return (
        <div className="nx-legend">
            {items.map((item) => <span key={item.label}><i data-tone={item.tone} aria-hidden="true" />{item.label}</span>)}
        </div>
    );
}
