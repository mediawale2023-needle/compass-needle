'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';

function cx(...classes) {
    return classes.filter(Boolean).join(' ');
}

const Icons = {
    Overview: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="7" height="7" />
            <rect x="14" y="3" width="7" height="7" />
            <rect x="14" y="14" width="7" height="7" />
            <rect x="3" y="14" width="7" height="7" />
        </svg>
    ),
    Profiles: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
        </svg>
    ),
    Geography: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21" />
            <line x1="9" y1="3" x2="9" y2="18" />
            <line x1="15" y1="6" x2="15" y2="21" />
        </svg>
    ),
    Rules: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
        </svg>
    ),
    Intelligence: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
    ),
    Health: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
    ),
    Analytics: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
        </svg>
    ),
    Staff: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
    ),
    Announcements: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 17H2a3 3 0 0 0 3-3V9a7 7 0 0 1 14 0v5a3 3 0 0 0 3 3zm-8.27 4a2 2 0 0 1-3.46 0" />
        </svg>
    ),
    Settings: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
    ),
    Audit: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
        </svg>
    ),
    Logout: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
        </svg>
    ),
    Constituency: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="10" r="3" />
            <path d="M12 2a8 8 0 0 0-8 8c0 5.25 8 13 8 13s8-7.75 8-13a8 8 0 0 0-8-8z" />
        </svg>
    ),
    Parliament: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="7" width="20" height="14" rx="2" />
            <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
            <line x1="12" y1="12" x2="12" y2="16" />
            <line x1="8" y1="12" x2="16" y2="12" />
        </svg>
    ),
    Brain: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.84A2.5 2.5 0 0 1 9.5 2Z" />
            <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.84A2.5 2.5 0 0 0 14.5 2Z" />
        </svg>
    ),
    Compass: () => (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="2" x2="12" y2="22" />
            <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
        </svg>
    ),
};

const NAV_GROUPS = [
    {
        label: 'Monitor',
        items: [
            { href: '/dashboard', label: 'Overview', Icon: Icons.Overview },
            { href: '/dashboard/health', label: 'Tenant Health', Icon: Icons.Health },
            { href: '/dashboard/intelligence', label: 'Case Intelligence', Icon: Icons.Intelligence },
            { href: '/dashboard/knowledge', label: 'Knowledge Sync', Icon: Icons.Constituency },
        ],
    },
    {
        label: 'Configure',
        items: [
            { href: '/dashboard/profiles', label: 'Profile Editor', Icon: Icons.Profiles },
            { href: '/dashboard/geography', label: 'Geography Upload', Icon: Icons.Geography },
            { href: '/dashboard/seat-maps', label: 'Seat Maps', Icon: Icons.Geography },
            { href: '/dashboard/rules', label: 'Geography Rules', Icon: Icons.Rules },
            { href: '/dashboard/staff', label: 'Staff Management', Icon: Icons.Staff },
        ],
    },
    {
        label: 'Communicate',
        items: [
            { href: '/dashboard/announcements', label: 'Announcements', Icon: Icons.Announcements },
        ],
    },
    {
        label: 'AI Brain',
        items: [
            { href: '/dashboard/brain', label: 'Intelligence Engine', Icon: Icons.Brain },
        ],
    },
    {
        label: 'Admin',
        items: [
            { href: '/dashboard/analytics', label: 'Usage Analytics', Icon: Icons.Analytics },
            { href: '/dashboard/audit', label: 'Audit Log', Icon: Icons.Audit },
            { href: '/dashboard/settings', label: 'Settings', Icon: Icons.Settings },
        ],
    },
];

export default function Sidebar() {
    const pathname = usePathname();
    const { user, logout } = useAuth();

    return (
        <aside className="fixed left-0 top-0 z-50 flex h-screen w-64 flex-col border-r border-[#e2ebe5] bg-white">
            <div className="flex h-16 items-center gap-3 border-b border-[#e2ebe5] px-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#006a4d] text-white shadow-sm">
                    <Icons.Compass />
                </div>
                <div className="min-w-0">
                    <h1 className="truncate text-sm font-bold text-[#1a2e28]">Compass Needle</h1>
                    <p className="truncate text-xs text-[#6b7f76]">Admin Console</p>
                </div>
            </div>

            <nav className="flex-1 overflow-y-auto px-2 py-3">
                {NAV_GROUPS.map((group) => (
                    <div key={group.label} className="mb-5">
                        <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#94a3a0]">
                            {group.label}
                        </div>
                        <div className="space-y-1">
                            {group.items.map((item) => {
                                const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));
                                return (
                                    <Link
                                        key={item.href}
                                        href={item.href}
                                        className={cx(
                                            'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200',
                                            isActive
                                                ? 'bg-[#006a4d]/10 text-[#006a4d]'
                                                : 'text-[#6b7f76] hover:bg-[#f4f7f5] hover:text-[#1a2e28]'
                                        )}
                                    >
                                        <span className={cx('shrink-0', isActive ? 'opacity-100' : 'opacity-75')}>
                                            <item.Icon />
                                        </span>
                                        <span className="truncate">{item.label}</span>
                                    </Link>
                                );
                            })}
                        </div>
                    </div>
                ))}
            </nav>

            <div className="border-t border-[#e2ebe5] p-3">
                <div className="mb-3 flex items-center gap-3 rounded-xl bg-[#f8faf9] px-3 py-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#e8efe9] text-sm font-semibold text-[#006a4d]">
                        {(user?.username || 'A')[0].toUpperCase()}
                    </div>
                    <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-[#1a2e28]">{user?.display_name || user?.username || 'Administrator'}</div>
                        <div className="truncate text-xs text-[#6b7f76]">Administrator</div>
                    </div>
                </div>

                <button
                    onClick={logout}
                    aria-label="Sign out"
                    className="flex w-full items-center justify-center gap-2 rounded-xl border border-[#e2ebe5] px-3 py-2.5 text-sm font-medium text-[#6b7f76] transition hover:border-red-200 hover:bg-red-50 hover:text-red-700"
                >
                    <Icons.Logout />
                    Sign out
                </button>
            </div>
        </aside>
    );
}
