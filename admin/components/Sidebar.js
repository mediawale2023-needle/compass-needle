'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import {
    LayoutDashboard, Users, UserPlus, Briefcase, MessageSquare,
    MapPin, Activity, Shield, ScrollText, LogOut, Menu,
} from 'lucide-react';

// Approved Admin IA: task-oriented top-level destinations. Existing routes and
// capabilities remain intact behind these entries. The brand block below is
// intentionally unchanged from the pre-redesign Admin.
const NAV_GROUPS = [
    {
        label: 'Command',
        items: [{ href: '/dashboard', label: 'Command Centre', icon: LayoutDashboard, exact: true }],
    },
    {
        label: 'Customers',
        items: [
            { href: '/dashboard/accounts', label: 'Accounts', icon: Users },
            { href: '/dashboard/accounts/new', label: 'Onboarding', icon: UserPlus },
        ],
    },
    {
        label: 'Operations',
        items: [
            { href: '/dashboard/cases-intelligence/explorer', label: 'Cases', icon: Briefcase },
            { href: '/dashboard/system/whatsapp', label: 'Messaging', icon: MessageSquare },
            { href: '/dashboard/seats', label: 'Data & Geography', icon: MapPin },
        ],
    },
    {
        label: 'Platform',
        items: [{ href: '/dashboard/system/health', label: 'System', icon: Activity }],
    },
    {
        label: 'Administration',
        items: [
            { href: '/dashboard/staff-access/users', label: 'People & Access', icon: Shield },
            { href: '/dashboard/staff-access/audit', label: 'Audit & Settings', icon: ScrollText },
        ],
    },
];

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
                <button type="button" className="admin-sidebar-backdrop" aria-label="Close navigation" onClick={onClose} />
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
                                const active = item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`);
                                const Icon = item.icon;
                                return (
                                    <Link href={item.href} key={item.href} className={`admin-nav-item ${active ? 'active' : ''}`}
                                        aria-current={active ? 'page' : undefined} onClick={onClose}>
                                        <Icon className="admin-nav-icon" size={14} strokeWidth={active ? 2 : 1.5} aria-hidden="true" />
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
