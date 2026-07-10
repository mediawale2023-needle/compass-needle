'use client';

import Image from 'next/image';
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
    Seats: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 8l8-4 8 4" />
            <path d="M6 10v8" />
            <path d="M10 8v10" />
            <path d="M14 8v10" />
            <path d="M18 10v8" />
            <path d="M3 20h18" />
        </svg>
    ),
    Cases: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
    ),
    System: () => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9" />
            <path d="M12 4h9" />
            <path d="M4 9h16" />
            <path d="M4 15h16" />
            <path d="M8 4v16" />
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
            { href: '/dashboard/accounts', label: 'Accounts', Icon: Icons.Profiles },
            { href: '/dashboard/seats', label: 'Seats', Icon: Icons.Seats },
        ],
    },
    {
        label: 'Configure',
        items: [
            { href: '/dashboard/seat-maps', label: 'Seat Maps', Icon: Icons.Geography },
            { href: '/dashboard/cases-intelligence', label: 'Cases & Intelligence', Icon: Icons.Cases },
        ],
    },
    {
        label: 'Operations',
        items: [
            { href: '/dashboard/staff-access', label: 'Staff & Access', Icon: Icons.Staff },
            { href: '/dashboard/system', label: 'System', Icon: Icons.System },
        ],
    },
];

export default function Sidebar() {
    const pathname = usePathname();
    const { user, logout } = useAuth();

    return (
        <aside className="fixed left-0 top-0 z-50 flex h-screen w-60 flex-col border-r border-[var(--chrome-line)] bg-[var(--chrome)] text-[var(--chrome-text)]">
            <div className="border-b border-[var(--chrome-line)] px-[18px] py-4">
                <Image
                    src="/needle-logo-cream.svg"
                    alt="Compass Needle"
                    width={63}
                    height={38}
                    className="h-[38px] w-auto"
                    priority
                />
                <div className="mt-[10px] min-w-0">
                    <p className="m-0 font-[var(--font-display)] text-[23px] font-semibold leading-[0.92] tracking-[-0.03em] text-[var(--chrome-hi)]">Compass</p>
                    <p className="m-0 font-[var(--font-display)] text-[23px] font-semibold leading-[0.92] tracking-[-0.03em] text-[var(--chrome-hi)]">Needle</p>
                    <p className="mt-2 truncate font-[var(--font-mono)] text-[9px] uppercase tracking-[0.18em] text-[var(--chrome-muted)]">Admin Console</p>
                </div>
            </div>

            <nav className="flex-1 overflow-y-auto px-[10px] py-[14px]">
                {NAV_GROUPS.map((group) => (
                    <div key={group.label} className="mb-[18px]">
                        <div className="px-3 pb-[10px] font-[var(--font-mono)] text-[9.5px] font-medium uppercase tracking-[0.18em] text-[var(--chrome-muted)]">
                            {group.label}
                        </div>
                        <div>
                            {group.items.map((item) => {
                                const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));
                                return (
                                    <Link
                                        key={item.href}
                                        href={item.href}
                                        className={cx(
                                            'mb-[3px] flex items-center gap-[11px] rounded-[5px] px-3 py-[9px] text-[13.5px] transition-all duration-200',
                                            isActive
                                                ? 'bg-[var(--sansad-green)] font-semibold text-white'
                                                : 'font-medium text-[var(--chrome-text)] opacity-90 hover:bg-[var(--chrome-2)] hover:text-[var(--chrome-hi)]'
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

            <div className="border-t border-[var(--chrome-line)] p-3">
                <div className="mb-[9px] flex items-center gap-[11px] rounded-[5px] bg-[var(--chrome-2)] px-[10px] py-[9px]">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--lok-deep,#084d38)] font-[var(--font-mono)] text-xs font-semibold text-[var(--chrome-hi)]">
                        {(user?.username || 'A')[0].toUpperCase()}
                    </div>
                    <div className="min-w-0">
                        <div className="truncate text-[13px] font-semibold text-[var(--chrome-hi)]">{user?.display_name || user?.username || 'Administrator'}</div>
                        <div className="truncate font-[var(--font-mono)] text-[10px] text-[var(--chrome-muted)]">Platform Admin</div>
                    </div>
                </div>

                <button
                    onClick={logout}
                    aria-label="Sign out"
                    className="flex w-full items-center justify-center gap-2 rounded-[5px] border border-[var(--chrome-line)] px-3 py-[9px] text-sm font-medium text-[var(--chrome-muted)] transition hover:border-[var(--chrome-muted)] hover:text-[var(--chrome-hi)]"
                >
                    <Icons.Logout />
                    Sign out
                </button>
            </div>
        </aside>
    );
}
