'use client';

import { avatarTintFor, initialsFor } from '@/lib/admin-data';
import { Check, X as XIcon } from 'lucide-react';

/**
 * Inline metric. A metric with no substantiating data renders "Unavailable"
 * rather than a misleading zero (the existing Admin rule).
 */
export function Metric({ label, value, detail, tone, unavailable = false, size = 'md' }) {
    const missing = unavailable || value === null || value === undefined;
    return (
        <div className="nx-metric" data-size={size} data-tone={missing ? undefined : tone}>
            <div className="nx-metric-label">{label}</div>
            <div className="nx-metric-value" data-unavailable={missing ? 'true' : undefined}>
                {missing ? 'Unavailable' : value}
            </div>
            {detail && !missing && <div className="nx-metric-detail">{detail}</div>}
        </div>
    );
}

/** A row of metrics separated by hairlines inside one bordered strip. */
export function MetricGroup({ children, columns }) {
    return <div className="nx-metric-group" style={columns ? { '--nx-cols': columns } : undefined}>{children}</div>;
}

/** Stacked proportional bar. segments = [{ value, tone, label }]; legend optional. */
export function SegmentBar({ segments = [], legend = true, label }) {
    const total = segments.reduce((sum, segment) => sum + Number(segment.value || 0), 0);
    return (
        <div className="nx-segbar">
            <div className="nx-segbar-track" role="img" aria-label={label || segments.map((s) => `${s.value} ${s.label}`).join(', ')}>
                {total > 0 && segments.filter((s) => Number(s.value) > 0).map((segment) => (
                    <span key={segment.label} data-tone={segment.tone} style={{ flexGrow: Number(segment.value) }} />
                ))}
            </div>
            {legend && (
                <div className="nx-legend">
                    {segments.map((segment) => (
                        <span key={segment.label}><i data-tone={segment.tone} aria-hidden="true" />{segment.value} {segment.label}</span>
                    ))}
                </div>
            )}
        </div>
    );
}

export function ProgressBar({ value, max = 100, tone = 'forest', label }) {
    const pct = max > 0 ? Math.max(0, Math.min(100, (Number(value) / Number(max)) * 100)) : 0;
    return (
        <div className="nx-progress" role="progressbar" aria-label={label} aria-valuenow={Number(value)} aria-valuemin={0} aria-valuemax={Number(max)}>
            <span data-tone={tone} style={{ width: `${pct}%` }} />
        </div>
    );
}

/** Label/value rows. items = [{ label, value, tone }]. */
export function KeyValueList({ items = [] }) {
    return (
        <dl className="nx-kv">
            {items.map((item) => (
                <div key={item.label} className="nx-kv-row">
                    <dt>{item.label}</dt>
                    <dd data-tone={item.tone}>{item.value ?? '—'}</dd>
                </div>
            ))}
        </dl>
    );
}

/** Vertical timeline. items = [{ title, meta, tone }]. */
export function Timeline({ items = [] }) {
    return (
        <ol className="nx-timeline">
            {items.map((item, index) => (
                <li key={`${item.meta}-${index}`}>
                    <span className="nx-timeline-dot" data-tone={item.tone} aria-hidden="true" />
                    <div className="nx-timeline-title">{item.title}</div>
                    {item.meta && <div className="nx-timeline-meta">{item.meta}</div>}
                </li>
            ))}
        </ol>
    );
}

export function Avatar({ name, size = 'md', tint, title }) {
    return (
        <span className={`nx-avatar nx-avatar-${size}`} data-tint={tint || avatarTintFor(name)} title={title} aria-hidden="true">
            {initialsFor(name)}
        </span>
    );
}

/** Avatar + name + secondary line (accounts, staff, citizens). */
export function AccountIdentity({ name, detail, size = 'md' }) {
    return (
        <span className="nx-identity">
            <Avatar name={name} size={size} />
            <span className="nx-identity-copy">
                <strong>{name}</strong>
                {detail && <small>{detail}</small>}
            </span>
        </span>
    );
}

/** Horizontal stepper. steps = [{ label, detail, state: 'done' | 'current' | 'todo' }]. */
export function Stepper({ steps = [], label = 'Progress' }) {
    const current = steps.findIndex((step) => step.state === 'current');
    return (
        <nav className="nx-stepper" aria-label={label}>
            <p className="nx-stepper-compact">Step {current + 1} of {steps.length} · {steps[current]?.label}</p>
            <ol>
                {steps.map((step, index) => (
                    <li key={step.label} className="nx-step" data-state={step.state} aria-current={step.state === 'current' ? 'step' : undefined}>
                        <span className="nx-step-n">{step.state === 'done' ? <Check size={14} strokeWidth={2.6} aria-hidden="true" /> : index + 1}</span>
                        <span>
                            <span className="nx-step-label">{step.label}</span>
                            {step.detail && <span className="nx-step-detail">{step.detail}</span>}
                        </span>
                        {index < steps.length - 1 && <span className="nx-step-line" aria-hidden="true" />}
                    </li>
                ))}
            </ol>
        </nav>
    );
}

const READINESS_TEXT = { complete: 'Complete', progress: 'In progress', todo: 'To do', blocked: 'Blocked', optional: 'Optional' };

export function ReadinessIcon({ state, size = 'md' }) {
    return (
        <span className="nx-ri" data-state={state} data-size={size} aria-hidden="true">
            {state === 'complete' && <Check strokeWidth={3} />}
            {state === 'blocked' && <XIcon strokeWidth={3} />}
        </span>
    );
}

/** Vertical readiness checklist. items = [{ label, detail, state, aside }]. */
export function ReadinessList({ items = [] }) {
    return (
        <ul className="nx-readiness">
            {items.map((item) => (
                <li key={item.label} data-state={item.state}>
                    <ReadinessIcon state={item.state} />
                    <span className="nx-readiness-copy">
                        <strong>{item.label}{item.state === 'optional' && <span className="nx-tag">Optional</span>}</strong>
                        <small><span className="nx-sr-only">{READINESS_TEXT[item.state]}. </span>{item.detail}</small>
                    </span>
                    {item.aside && <span className="nx-muted nx-readiness-aside">{item.aside}</span>}
                </li>
            ))}
        </ul>
    );
}

/** Horizontal readiness columns (Account 360). items = [{ label, tone, status, detail, icon }]. */
export function ReadinessRail({ items = [] }) {
    return (
        <div className="nx-rail" style={{ '--nx-cols': items.length }}>
            {items.map((item) => {
                const Icon = item.icon;
                return (
                    <div key={item.label} className="nx-rail-cell" data-tone={item.tone}>
                        <div className="nx-rail-head">
                            <span>{item.label}</span>
                            {Icon && <Icon size={16} strokeWidth={1.75} aria-hidden="true" />}
                        </div>
                        <span className="nx-status" data-tone={item.tone}><span className="nx-dot" data-tone={item.tone} aria-hidden="true" />{item.status}</span>
                        {item.detail && <div className="nx-rail-detail">{item.detail}</div>}
                    </div>
                );
            })}
        </div>
    );
}
