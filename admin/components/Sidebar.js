'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { NAV_GROUPS, activeNavItem } from '@/lib/admin-nav';
import { useAdminSignals } from '@/lib/admin-signals';
import { NAV_ICONS, Menu, X } from '@/components/admin-ui/icons';

export { NAV_GROUPS };

export function MenuIcon(props) {
    return <Menu aria-hidden="true" {...props} />;
}

const COUNT_LABEL = { critical: 'critical', warning: 'warning', review: 'to review' };

function NavCount({ signal }) {
    if (!signal?.count) return null;
    const tone = signal.severity === 'critical' || signal.severity === 'warning' || signal.severity === 'review' ? signal.severity : 'neutral';
    return (
        <>
            <span className="nx-nav-count" data-tone={tone} aria-hidden="true">{signal.count}</span>
            <span className="nx-sr-only">{`, ${signal.count} ${COUNT_LABEL[signal.severity] || 'alerts'}`}</span>
        </>
    );
}

function ConditionCard({ condition }) {
    if (!condition) return null;
    if (condition.severity === 'ok') {
        return (
            <Link href="/dashboard/system/health" className="nx-condition nx-condition-quiet">
                <span className="nx-dot" data-tone="ok" aria-hidden="true" />
                {condition.title}
            </Link>
        );
    }
    return (
        <Link href="/dashboard/system/health" className="nx-condition" data-tone={condition.severity}>
            <span className="nx-condition-title">
                <span className="nx-dot nx-dot-ring" data-tone={condition.severity} aria-hidden="true" />
                {condition.title}
            </span>
            {condition.detail && <span className="nx-condition-detail">{condition.detail}</span>}
            <span className="nx-condition-link">View system health →</span>
        </Link>
    );
}

export default function Sidebar({ open = false, onClose }) {
    const pathname = usePathname();
    const { signals, condition } = useAdminSignals();
    const active = activeNavItem(pathname);

    return (
        <>
            {open && (
                <button type="button" className="nx-sidebar-backdrop" aria-label="Close navigation" onClick={onClose} />
            )}
            <aside className="nx-sidebar" data-open={open ? 'true' : 'false'} aria-label="Needle Admin">
                <div className="nx-brand-row">
                    <Link href="/dashboard" className="nx-brand" onClick={onClose}>
                        <span className="nx-brand-mark">
                            <Image src="/needle-logo-cream.svg" alt="" width={26} height={22} priority />
                        </span>
                        <span className="nx-brand-copy">
                            <strong>Needle</strong>
                            <small>Admin console</small>
                        </span>
                    </Link>
                    <button type="button" className="nx-icon-button nx-sidebar-close" aria-label="Close navigation" onClick={onClose}>
                        <X size={16} strokeWidth={1.9} aria-hidden="true" />
                    </button>
                </div>

                <nav className="nx-sidebar-nav" aria-label="Primary">
                    {NAV_GROUPS.map((group) => (
                        <section className="nx-nav-group" key={group.label} aria-label={group.label}>
                            <div className="nx-nav-heading">{group.label}</div>
                            {group.items.map((item) => {
                                const isActive = active?.id === item.id;
                                const Icon = NAV_ICONS[item.icon];
                                return (
                                    <Link
                                        key={item.id}
                                        href={item.href}
                                        className="nx-nav-item"
                                        data-active={isActive ? 'true' : undefined}
                                        aria-current={isActive ? 'page' : undefined}
                                        onClick={onClose}
                                    >
                                        {Icon && <Icon className="nx-nav-icon" size={18} strokeWidth={1.75} aria-hidden="true" />}
                                        <span className="nx-nav-label">{item.label}</span>
                                        <NavCount signal={signals?.[item.id]} />
                                    </Link>
                                );
                            })}
                        </section>
                    ))}
                </nav>

                <div className="nx-sidebar-footer">
                    <ConditionCard condition={condition} />
                </div>
            </aside>
        </>
    );
}
