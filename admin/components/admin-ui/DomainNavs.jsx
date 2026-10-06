'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { AdminSectionNav } from './AdminPrimitives';

const CASE_OPERATIONS_ITEMS = [
    { label: 'Case Explorer', href: '/dashboard/cases-intelligence/explorer' },
    { label: 'Knowledge', href: '/dashboard/cases-intelligence/knowledge' },
    { label: 'Constituency Profiles', href: '/dashboard/constituency' },
    { label: 'AI Engine', href: '/dashboard/cases-intelligence/engine' },
    { label: 'Usage Analytics', href: '/dashboard/cases-intelligence/analytics' },
];
const PLATFORM_ITEMS = [
    { label: 'Parliament Sync', href: '/dashboard/system/parliament-sync' },
    { label: 'System Health', href: '/dashboard/system/health' },
    { label: 'Jobs', href: '/dashboard/system/jobs' },
    { label: 'Announcements', href: '/dashboard/system/announcements' },
    { label: 'Settings', href: '/dashboard/system/settings' },
];
const MESSAGING_ITEMS = [
    { label: 'Overview', href: '/dashboard/system/whatsapp#overview', section: 'overview' },
    { label: 'Inbound', href: '/dashboard/system/whatsapp-inbound', route: '/dashboard/system/whatsapp-inbound' },
    { label: 'Outbound', href: '/dashboard/system/whatsapp#outbound', section: 'outbound' },
    { label: 'Failures', href: '/dashboard/system/whatsapp#failures', section: 'failures' },
    { label: 'Routing', href: '/dashboard/system/whatsapp#routing', section: 'routing' },
];
const ADMINISTRATION_ITEMS = [
    { label: 'Staff & Access', href: '/dashboard/staff-access/users' },
    { label: 'Audit Log', href: '/dashboard/staff-access/audit' },
    { label: 'Announcements', href: '/dashboard/system/announcements' },
    { label: 'Settings', href: '/dashboard/system/settings' },
];
const CONSTITUENCY_ITEMS = [
    { label: 'Seat Registry', href: '/dashboard/seats' },
    { label: 'Geography', href: '/dashboard/shared-geography/workspace' },
    { label: 'Seat Maps', href: '/dashboard/seat-maps' },
];

export function CaseOperationsNav() { return <AdminSectionNav label="Case Operations" items={CASE_OPERATIONS_ITEMS} />; }
export function PlatformOperationsNav() {
    const pathname = usePathname();
    if (pathname.startsWith('/dashboard/system/whatsapp')) return null;
    return <AdminSectionNav label="Platform Operations" items={PLATFORM_ITEMS} />;
}
export function AdministrationNav() { return <AdminSectionNav label="Administration" items={ADMINISTRATION_ITEMS} />; }
export function ConstituencyNav() { return <AdminSectionNav label="Constituencies" items={CONSTITUENCY_ITEMS} />; }

export function MessagingNav() {
    const pathname = usePathname();
    const [hash, setHash] = useState('');

    useEffect(() => {
        const syncHash = () => setHash(window.location.hash.slice(1));
        syncHash();
        window.addEventListener('hashchange', syncHash);
        return () => window.removeEventListener('hashchange', syncHash);
    }, [pathname]);

    return (
        <nav className="admin-section-nav messaging-local-nav" aria-label="Messaging operations">
            {MESSAGING_ITEMS.map((item) => {
                const active = item.route
                    ? pathname === item.route
                    : pathname === '/dashboard/system/whatsapp' && (hash || 'overview') === item.section;
                return <Link key={item.href} href={item.href} aria-current={active ? 'page' : undefined}>{item.label}</Link>;
            })}
        </nav>
    );
}
