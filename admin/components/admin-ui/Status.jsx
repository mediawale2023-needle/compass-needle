'use client';

import { SEVERITY_LABEL } from '@/lib/admin-data';
import { CircleAlert, TriangleAlert, Info, CircleCheck } from 'lucide-react';

/** Tones: critical | warning | review | notice | ok | neutral. */
export function Badge({ tone = 'neutral', dot = true, children }) {
    return (
        <span className="nx-badge" data-tone={tone}>
            {dot && <i aria-hidden="true" />}
            {children}
        </span>
    );
}

export function SeverityBadge({ severity }) {
    return <Badge tone={severity}>{SEVERITY_LABEL[severity] || severity}</Badge>;
}

export function StatusDot({ tone = 'neutral', ring = false }) {
    return <span className={`nx-dot ${ring ? 'nx-dot-ring' : ''}`} data-tone={tone} aria-hidden="true" />;
}

/** Dot + label status, e.g. "● Operational". */
export function StatusText({ tone = 'neutral', children }) {
    return (
        <span className="nx-status" data-tone={tone}>
            <StatusDot tone={tone} />
            {children}
        </span>
    );
}

const SEVERITY_ICON = { critical: CircleAlert, warning: TriangleAlert, review: Info, notice: Info, ok: CircleCheck, neutral: Info };

/** Rounded icon tile tinted by severity. Pass `icon` (a lucide component) to override. */
export function SeverityTile({ tone = 'neutral', icon, size = 'md' }) {
    const Icon = icon || SEVERITY_ICON[tone] || Info;
    return (
        <span className="nx-tile" data-tone={tone} data-size={size} aria-hidden="true">
            <Icon size={size === 'lg' ? 20 : size === 'sm' ? 14 : 18} strokeWidth={1.75} />
        </span>
    );
}

/**
 * Incident banner (Account 360 / Messaging pattern): prominent but not a
 * full error page. `metrics` = [{ value, label, tone }].
 */
export function IncidentBanner({ severity = 'critical', icon, title, meta, detail, metrics = [], actions }) {
    return (
        <section className="nx-incident" data-tone={severity} role={severity === 'critical' ? 'alert' : 'status'}>
            <SeverityTile tone={severity} icon={icon} size="lg" />
            <div className="nx-incident-body">
                <div className="nx-incident-meta">
                    <SeverityBadge severity={severity} />
                    {meta && <span className="nx-muted">{meta}</span>}
                </div>
                <div className="nx-incident-title">{title}</div>
                {detail && <div className="nx-incident-detail">{detail}</div>}
            </div>
            {metrics.length > 0 && (
                <div className="nx-incident-metrics">
                    {metrics.map((metric) => (
                        <div key={metric.label} className="nx-incident-metric" data-tone={metric.tone}>
                            <strong>{metric.value}</strong>
                            <span>{metric.label}</span>
                        </div>
                    ))}
                </div>
            )}
            {actions && <div className="nx-incident-actions">{actions}</div>}
        </section>
    );
}

/** One-line platform condition (System pattern). `segments` = [{ tone }]. */
export function ConditionStrip({ severity = 'ok', title, summary, segments = [], note }) {
    return (
        <section className="nx-card nx-condition-strip" aria-label="Condition">
            <div className="nx-condition-lead">
                <StatusDot tone={severity} ring />
                <strong>{title}</strong>
                {summary && <span className="nx-muted">{summary}</span>}
            </div>
            {segments.length > 0 && (
                <div className="nx-condition-segments" aria-hidden="true">
                    {segments.map((segment, index) => <span key={index} data-tone={segment.tone} />)}
                </div>
            )}
            {note && <span className="nx-muted nx-condition-note">{note}</span>}
        </section>
    );
}
