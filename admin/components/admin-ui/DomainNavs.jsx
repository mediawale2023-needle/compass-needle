'use client';

import { AdminSectionNav } from './AdminPrimitives';

const CASE_OPERATIONS_ITEMS = [
    { label: 'Case Intelligence', href: '/dashboard/cases-intelligence/explorer' },
    { label: 'Knowledge', href: '/dashboard/cases-intelligence/knowledge' },
    { label: 'Constituency Profiles', href: '/dashboard/constituency' },
    { label: 'AI Engine', href: '/dashboard/cases-intelligence/engine' },
    { label: 'Usage Analytics', href: '/dashboard/cases-intelligence/analytics' },
];
const PLATFORM_ITEMS = [
    { label: 'WhatsApp Overview', href: '/dashboard/system/whatsapp' },
    { label: 'Inbound', href: '/dashboard/system/whatsapp-inbound' },
    { label: 'Parliament Sync', href: '/dashboard/system/parliament-sync' },
    { label: 'System Health', href: '/dashboard/system/health' },
    { label: 'Jobs', href: '/dashboard/system/jobs' },
    { label: 'Announcements', href: '/dashboard/system/announcements' },
    { label: 'Settings', href: '/dashboard/system/settings' },
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
export function PlatformOperationsNav() { return <AdminSectionNav label="Messaging and Platform Operations" items={PLATFORM_ITEMS} />; }
export function AdministrationNav() { return <AdminSectionNav label="Administration" items={ADMINISTRATION_ITEMS} />; }
export function ConstituencyNav() { return <AdminSectionNav label="Constituencies" items={CONSTITUENCY_ITEMS} />; }
