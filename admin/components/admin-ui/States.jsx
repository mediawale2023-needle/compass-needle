'use client';

export function LoadingSkeleton({ rows = 4, label = 'Loading' }) {
    return (
        <div className="nx-skeleton-stack" aria-label={label} aria-busy="true">
            {Array.from({ length: rows }, (_, index) => <div className="nx-skeleton" key={index} />)}
        </div>
    );
}

export function EmptyState({ title, description, action }) {
    return (
        <div className="nx-empty">
            <strong>{title}</strong>
            {description && <p>{description}</p>}
            {action}
        </div>
    );
}

export function ErrorState({ title = 'Data unavailable', message, onRetry }) {
    return (
        <div className="nx-callout" data-tone="critical" role="alert">
            <div className="nx-callout-body"><strong>{title}. </strong>{message}</div>
            {onRetry && <div className="nx-callout-action"><button type="button" className="nx-btn nx-btn-sm" onClick={onRetry}>Try again</button></div>}
        </div>
    );
}

/** Inline marker for a value Needle cannot currently substantiate. */
export function Unavailable({ children = 'Unavailable', title = 'This data is not available from Needle yet' }) {
    return <span className="nx-unavailable" title={title}>{children}</span>;
}

/** Loading / error / empty switch, mirroring AdminDataState with the new visuals. */
export function DataState({ loading, error, empty, emptyTitle = 'Nothing to show', emptyDescription, onRetry, rows = 4, children }) {
    if (loading) return <LoadingSkeleton rows={rows} />;
    if (error) return <ErrorState message={error} onRetry={onRetry} />;
    if (empty) return <EmptyState title={emptyTitle} description={emptyDescription} />;
    return children;
}
