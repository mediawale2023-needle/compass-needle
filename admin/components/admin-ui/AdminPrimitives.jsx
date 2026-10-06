'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function AdminPageHeader({ title, description, actions, context }) {
    return (
        <div className="admin-page-header">
            <div className="admin-page-heading">
                {context && <div className="admin-context-line">{context}</div>}
                <h2>{title}</h2>
                {description && <p>{description}</p>}
            </div>
            {actions && <div className="admin-page-actions">{actions}</div>}
        </div>
    );
}

export function AdminSectionNav({ label, items }) {
    const pathname = usePathname();
    return (
        <nav className="admin-section-nav" aria-label={label}>
            {items.map((item) => {
                const active = pathname === item.href || (item.matchChildren && pathname.startsWith(`${item.href}/`));
                return (
                    <Link key={item.href} href={item.href} aria-current={active ? 'page' : undefined}>
                        {item.label}
                    </Link>
                );
            })}
        </nav>
    );
}

export function AdminPanel({ title, description, actions, children, className = '' }) {
    return (
        <section className={`admin-panel ${className}`.trim()}>
            {(title || description || actions) && (
                <div className="admin-panel-header">
                    <div>
                        {title && <h3>{title}</h3>}
                        {description && <p>{description}</p>}
                    </div>
                    {actions && <div className="admin-panel-actions">{actions}</div>}
                </div>
            )}
            {children}
        </section>
    );
}

export function AdminNotice({ tone = 'info', title, children, action }) {
    return (
        <div className={`admin-notice admin-notice-${tone}`} role={tone === 'danger' ? 'alert' : 'status'}>
            <div>
                {title && <strong>{title}</strong>}
                {children && <p>{children}</p>}
            </div>
            {action && <div className="admin-notice-action">{action}</div>}
        </div>
    );
}

export function AdminDataState({ loading, error, empty, emptyTitle = 'No records found', emptyDescription, onRetry, children, skeletonRows = 4 }) {
    if (loading) {
        return (
            <div className="admin-state-stack" aria-label="Loading" aria-busy="true">
                {Array.from({ length: skeletonRows }, (_, index) => <div className="admin-skeleton-row" key={index} />)}
            </div>
        );
    }
    if (error) {
        return (
            <AdminNotice
                tone="danger"
                title="Data unavailable"
                action={onRetry ? <button type="button" className="btn-secondary" onClick={onRetry}>Try again</button> : null}
            >
                {error}
            </AdminNotice>
        );
    }
    if (empty) {
        return (
            <div className="admin-empty-state">
                <h3>{emptyTitle}</h3>
                {emptyDescription && <p>{emptyDescription}</p>}
            </div>
        );
    }
    return children;
}

// `unavailable` may be set for the whole strip (existing behaviour) or per
// item, so one counter whose source failed does not force every other
// counter to claim it is unavailable too. A counter never shows a zero it
// cannot substantiate.
export function AdminMetricStrip({ items, unavailable = false }) {
    return (
        <dl className="admin-metric-strip">
            {items.map((item) => {
                const isUnavailable = unavailable || item.unavailable;
                return (
                    <div key={item.label} data-tone={isUnavailable ? 'neutral' : (item.tone || 'neutral')}>
                        <dt>{item.label}</dt>
                        <dd data-unavailable={isUnavailable ? 'true' : undefined}>
                            {isUnavailable ? 'Unavailable' : item.value}
                        </dd>
                        {item.detail && !isUnavailable && <span>{item.detail}</span>}
                    </div>
                );
            })}
        </dl>
    );
}

export function AdminMetricCards({ items, unavailable = false }) {
    return (
        <dl className="admin-metric-cards">
            {items.map((item) => {
                const isUnavailable = unavailable || item.unavailable;
                return (
                    <div key={item.label} data-tone={isUnavailable ? 'neutral' : (item.tone || 'neutral')}>
                        <dt>{item.label}</dt>
                        <dd data-unavailable={isUnavailable ? 'true' : undefined}>
                            {isUnavailable ? 'Unavailable' : item.value}
                        </dd>
                        <span>{isUnavailable ? 'Source could not be verified' : (item.detail || 'Current operational state')}</span>
                    </div>
                );
            })}
        </dl>
    );
}

export function AdminStatus({ tone = 'neutral', label, detail }) {
    return (
        <span className="admin-status" data-tone={tone}>
            <i aria-hidden="true" />
            <span><strong>{label}</strong>{detail && <small>{detail}</small>}</span>
        </span>
    );
}

export function AdminTableWrap({ label, children }) {
    return (
        <div className="admin-table-region" role="region" aria-label={label} tabIndex="0">
            {children}
        </div>
    );
}
