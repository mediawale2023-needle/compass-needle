'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import {
    LayoutDashboard,
    Users,
    UserPlus,
    MapPin,
    Map,
    Briefcase,
    MessageSquare,
    Inbox,
    RefreshCw,
    Activity,
    ListChecks,
    Shield,
    ScrollText,
    Megaphone,
    Settings,
    LogOut,
    Menu,
} from 'lucide-react';

// Primary rail. Deliberately one line per destination and no counts — the
// rail's job is orientation, not reporting.
//
// Case Operations collapses to a single primary entry; Knowledge, AI Engine,
// Usage Analytics and Constituency Profiles remain reachable through the
// CaseOperationsNav secondary tier mounted by
// app/dashboard/cases-intelligence/layout.js. The same holds for Geography
// under Constituencies and for Account Registry/Create under Customers. No
// destination was removed.
const NAV_GROUPS = [
    {
        label: 'Overview',
        items: [
            { href: '/dashboard', label: 'Command Centre', icon: LayoutDashboard, exact: true },
        ],
    },
    {
        label: 'Customers',
        items: [
            { href: '/dashboard/accounts', label: 'Accounts', icon: Users },
            { href: '/dashboard/accounts/new', label: 'Onboarding', icon: UserPlus },
        ],
    },
    {
        label: 'Constituencies',
        items: [
            { href: '/dashboard/seats', label: 'Seats & Geography', icon: MapPin },
            { href: '/dashboard/seat-maps', label: 'Seat Maps', icon: Map },
        ],
    },
    {
        label: 'Case Operations',
        items: [
            { href: '/dashboard/cases-intelligence/explorer', label: 'Case Intelligence', icon: Briefcase },
        ],
    },
    {
        label: 'Messaging & Sync',
        items: [
            { href: '/dashboard/system/whatsapp', label: 'WhatsApp Operations', icon: MessageSquare },
            { href: '/dashboard/system/whatsapp-inbound', label: 'Inbound', icon: Inbox },
            { href: '/dashboard/system/parliament-sync', label: 'Parliament Sync', icon: RefreshCw },
        ],
    },
    {
        label: 'Platform Operations',
        items: [
            { href: '/dashboard/system/health', label: 'System Health', icon: Activity },
            { href: '/dashboard/system/jobs', label: 'Jobs', icon: ListChecks },
        ],
    },
    {
        label: 'Administration',
        items: [
            { href: '/dashboard/staff-access/users', label: 'Staff & Access', icon: Shield },
            { href: '/dashboard/staff-access/audit', label: 'Audit Log', icon: ScrollText },
            { href: '/dashboard/system/announcements', label: 'Announcements', icon: Megaphone },
            { href: '/dashboard/system/settings', label: 'Settings', icon: Settings },
        ],
    },
];

// Exported so the shell can offer the same destinations without duplicating
// the list.
export { NAV_GROUPS };

export function MenuIcon(props) {
    return <Menu aria-hidden="true" {...props} />;
}

export default function Sidebar({ open = false, onClose }) {
    const pathname = usePathname();
    const { user, logout } = useAuth();
    const initials = (user?.display_name || user?.username || 'A').slice(0, 1).toUpperCase();

    return (
        <>
            {open && (
                <button
                    type="button"
                    className="admin-sidebar-backdrop"
                    aria-label="Close navigation"
                    onClick={onClose}
                />
            )}
            <aside className="admin-sidebar" data-open={open ? 'true' : 'false'}>
                <div className="admin-sidebar-brand">
                    <Image src="/needle-logo-cream.svg" alt="Needle" width={60} height={36} priority />
                    <div className="admin-brand-name">Needle</div>
                    <div className="admin-brand-label">Admin Console</div>
                </div>

                <nav className="admin-sidebar-nav">
                    {NAV_GROUPS.map((group) => (
                        <section className="admin-nav-group" key={group.label}>
                            <div className="admin-nav-heading">{group.label}</div>
                            {group.items.map((item) => {
                                const active = item.exact
                                    ? pathname === item.href
                                    : pathname === item.href || pathname.startsWith(`${item.href}/`);
                                const Icon = item.icon;
                                return (
                                    <Link
                                        href={item.href}
                                        key={item.href}
                                        className={`admin-nav-item ${active ? 'active' : ''}`}
                                        aria-current={active ? 'page' : undefined}
                                        onClick={onClose}
                                    >
                                        <Icon
                                            className="admin-nav-icon"
                                            size={14}
                                            strokeWidth={active ? 2 : 1.5}
                                            aria-hidden="true"
                                        />
                                        <span className="admin-nav-label">{item.label}</span>
                                    </Link>
                                );
                            })}
                        </section>
                    ))}
                </nav>

                <div className="admin-sidebar-footer">
                    <div className="admin-user">
                        <span className="admin-user-avatar" aria-hidden="true">{initials}</span>
                        <span className="admin-user-copy">
                            <strong>{user?.display_name || user?.username || 'Administrator'}</strong>
                            <small>Platform Admin</small>
                        </span>
                        <button onClick={logout} className="admin-signout" aria-label="Sign out" type="button">
                            <LogOut size={16} strokeWidth={1.5} aria-hidden="true" />
                        </button>
                    </div>
                </div>
            </aside>
        </>
    );
}
