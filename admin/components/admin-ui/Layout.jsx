'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

/** Page title block on the workspace background (Command Centre / Onboarding pattern). */
export function PageHeader({ title, description, meta, actions, eyebrow }) {
    return (
        <div className="nx-page-header">
            <div className="nx-page-heading">
                {eyebrow && <div className="nx-eyebrow">{eyebrow}</div>}
                <h1>{title}</h1>
                {(description || meta) && (
                    <p className="nx-page-description">
                        {description}
                        {description && meta && <span className="nx-sep" aria-hidden="true">·</span>}
                        {meta}
                    </p>
                )}
            </div>
            {actions && <div className="nx-page-actions">{actions}</div>}
        </div>
    );
}

/** White band under the top bar carrying the title and local tabs (Cases / Messaging pattern). */
export function PageBand({ title, description, meta, actions, tabs, children }) {
    return (
        <section className="nx-band">
            <div className="nx-band-row">
                <div className="nx-page-heading">
                    <h1>{title}</h1>
                    {(description || meta) && (
                        <p className="nx-page-description">
                            {description}
                            {description && meta && <span className="nx-sep" aria-hidden="true">·</span>}
                            {meta}
                        </p>
                    )}
                </div>
                {actions && <div className="nx-page-actions">{actions}</div>}
            </div>
            {children}
            {tabs}
        </section>
    );
}

function useHash(pathname) {
    const [hash, setHash] = useState('');
    useEffect(() => {
        const sync = () => setHash(window.location.hash.slice(1));
        sync();
        window.addEventListener('hashchange', sync);
        return () => window.removeEventListener('hashchange', sync);
    }, [pathname]);
    return hash;
}

/**
 * Local navigation. Items: { label, href, count?, tone?, section?, route?, matchChildren? }.
 * - `section` items are hash sections of `route` (default section = first).
 * - otherwise active when pathname === href (or a child, with matchChildren).
 */
export function LocalTabs({ label, items, defaultSection }) {
    const pathname = usePathname();
    const hash = useHash(pathname);
    const firstSection = defaultSection || items.find((item) => item.section)?.section;
    return (
        <nav className="nx-tabs" aria-label={label}>
            {items.map((item) => {
                const base = item.href.split('#')[0];
                let active;
                if (item.section) active = pathname === (item.route || base) && (hash || firstSection) === item.section;
                else active = pathname === base || (item.matchChildren && pathname.startsWith(`${base}/`));
                return (
                    <Link key={item.href} href={item.href} className="nx-tab" aria-current={active ? 'page' : undefined}>
                        {item.label}
                        {item.count !== undefined && item.count !== null && (
                            <span className="nx-count" data-tone={item.tone || 'neutral'}>{item.count}</span>
                        )}
                    </Link>
                );
            })}
        </nav>
    );
}

/** Card surface. `tone` tints problem cards (critical | warning | ok | info). */
export function Card({ title, description, actions, footer, children, tone, padded = false, className = '', as: Tag = 'section', ...rest }) {
    return (
        <Tag className={`nx-card ${padded ? 'nx-card-padded' : ''} ${className}`.trim()} data-tone={tone} {...rest}>
            {(title || description || actions) && (
                <div className="nx-card-head">
                    <div>
                        {title && <h2 className="nx-card-title">{title}</h2>}
                        {description && <p className="nx-card-description">{description}</p>}
                    </div>
                    {actions && <div className="nx-card-actions">{actions}</div>}
                </div>
            )}
            {children}
            {footer && <div className="nx-card-foot">{footer}</div>}
        </Tag>
    );
}

/** Two-column grid: wide main + narrow side (stacks below 1100px). */
export function SplitGrid({ children, align = 'start', ratio = 'wide' }) {
    return <div className="nx-split-grid" data-ratio={ratio} data-align={align}>{children}</div>;
}

/**
 * Master/detail workspace. On desktop the detail sits beside the master;
 * below 1024px it becomes a drawer opened when `detailOpen` is true.
 */
export function SplitView({ master, detail, detailLabel = 'Details', detailOpen = true, onCloseDetail }) {
    return (
        <div className="nx-splitview" data-detail-open={detailOpen ? 'true' : 'false'}>
            <div className="nx-splitview-master">{master}</div>
            {detail && (
                <>
                    {detailOpen && onCloseDetail && (
                        <button type="button" className="nx-drawer-backdrop" aria-label={`Close ${detailLabel}`} onClick={onCloseDetail} />
                    )}
                    <aside className="nx-splitview-detail" aria-label={detailLabel}>{detail}</aside>
                </>
            )}
        </div>
    );
}

export function TextLink({ href, children }) {
    return <Link href={href} className="nx-link">{children}</Link>;
}
