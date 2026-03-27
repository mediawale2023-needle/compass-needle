'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';

const Icons = {
    Overview: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
            <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
        </svg>
    ),
    Profiles: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
        </svg>
    ),
    Geography: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"/>
            <line x1="9" y1="3" x2="9" y2="18"/><line x1="15" y1="6" x2="15" y2="21"/>
        </svg>
    ),
    Rules: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
        </svg>
    ),
    Intelligence: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
    ),
    Health: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
        </svg>
    ),
    Analytics: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/>
            <line x1="6" y1="20" x2="6" y2="14"/>
        </svg>
    ),
    Staff: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
    ),
    Announcements: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 17H2a3 3 0 0 0 3-3V9a7 7 0 0 1 14 0v5a3 3 0 0 0 3 3zm-8.27 4a2 2 0 0 1-3.46 0"/>
        </svg>
    ),
    Settings: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
    ),
    Audit: () => (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
        </svg>
    ),
    Logout: () => (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
        </svg>
    ),
};

const NAV_GROUPS = [
    {
        label: 'MONITOR',
        items: [
            { href: '/dashboard', label: 'Overview', Icon: Icons.Overview },
            { href: '/dashboard/health', label: 'Tenant Health', Icon: Icons.Health },
            { href: '/dashboard/intelligence', label: 'Case Intelligence', Icon: Icons.Intelligence },
        ],
    },
    {
        label: 'CONFIGURE',
        items: [
            { href: '/dashboard/profiles', label: 'Profile Editor', Icon: Icons.Profiles },
            { href: '/dashboard/geography', label: 'Geography Upload', Icon: Icons.Geography },
            { href: '/dashboard/rules', label: 'Geography Rules', Icon: Icons.Rules },
            { href: '/dashboard/staff', label: 'Staff Management', Icon: Icons.Staff },
        ],
    },
    {
        label: 'COMMUNICATE',
        items: [
            { href: '/dashboard/announcements', label: 'Announcements', Icon: Icons.Announcements },
        ],
    },
    {
        label: 'ADMIN',
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
        <aside style={{
            width: 240,
            minHeight: '100vh',
            background: '#ffffff',
            borderRight: '1px solid #e2ebe5',
            display: 'flex',
            flexDirection: 'column',
            position: 'fixed',
            top: 0,
            left: 0,
            zIndex: 50,
        }}>
            {/* Logo */}
            <div style={{ padding: '1.25rem 1.25rem 1.1rem', borderBottom: '1px solid #e2ebe5' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                    <div style={{
                        width: 30, height: 30, borderRadius: 8,
                        background: 'linear-gradient(135deg, #006a4d, #00875f)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexShrink: 0,
                    }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="12" y1="2" x2="12" y2="22"/>
                            <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                        </svg>
                    </div>
                    <div>
                        <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#006a4d', letterSpacing: '-0.3px', lineHeight: 1.2 }}>
                            Needle
                        </div>
                        <div style={{ fontSize: '0.62rem', color: '#6b7f76', fontWeight: 500, letterSpacing: '0.6px', textTransform: 'uppercase' }}>
                            Command Center
                        </div>
                    </div>
                </div>
            </div>

            {/* Grouped Nav */}
            <nav style={{ flex: 1, padding: '0.5rem 0.75rem', overflowY: 'auto' }}>
                {NAV_GROUPS.map((group, gi) => (
                    <div key={group.label} style={{ marginBottom: gi < NAV_GROUPS.length - 1 ? 6 : 0 }}>
                        <div style={{
                            fontSize: '0.58rem',
                            fontWeight: 700,
                            color: '#94a3a0',
                            letterSpacing: '1.6px',
                            textTransform: 'uppercase',
                            padding: '10px 12px 4px',
                        }}>
                            {group.label}
                        </div>
                        {group.items.map((item) => {
                            const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));
                            return (
                                <Link
                                    key={item.href}
                                    href={item.href}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 9,
                                        padding: '7px 12px',
                                        borderRadius: 8,
                                        marginBottom: 1,
                                        fontSize: '0.83rem',
                                        fontWeight: isActive ? 600 : 450,
                                        color: isActive ? '#006a4d' : '#6b7f76',
                                        background: isActive ? 'rgba(0, 106, 77, 0.08)' : 'transparent',
                                        textDecoration: 'none',
                                        transition: 'all 0.12s ease',
                                        borderLeft: isActive ? '2.5px solid #006a4d' : '2.5px solid transparent',
                                        position: 'relative',
                                    }}
                                    onMouseEnter={e => {
                                        if (!isActive) {
                                            e.currentTarget.style.background = '#f4f7f5';
                                            e.currentTarget.style.color = '#1a2e28';
                                        }
                                    }}
                                    onMouseLeave={e => {
                                        if (!isActive) {
                                            e.currentTarget.style.background = 'transparent';
                                            e.currentTarget.style.color = '#6b7f76';
                                        }
                                    }}
                                >
                                    <span style={{ flexShrink: 0, opacity: isActive ? 1 : 0.7 }}>
                                        <item.Icon />
                                    </span>
                                    {item.label}
                                </Link>
                            );
                        })}
                    </div>
                ))}
            </nav>

            {/* Footer */}
            <div style={{ padding: '0.875rem 1rem', borderTop: '1px solid #e2ebe5' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 8 }}>
                    <div style={{
                        width: 28, height: 28, borderRadius: 7,
                        background: 'linear-gradient(135deg, #e8efe9, #d4e0d9)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '0.7rem', fontWeight: 700, color: '#006a4d', flexShrink: 0,
                    }}>
                        {(user?.username || 'A')[0].toUpperCase()}
                    </div>
                    <div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#1a2e28', lineHeight: 1.2 }}>
                            {user?.username || 'admin'}
                        </div>
                        <div style={{ fontSize: '0.65rem', color: '#6b7f76' }}>Administrator</div>
                    </div>
                </div>
                <button
                    onClick={logout}
                    style={{
                        width: '100%',
                        padding: '7px 12px',
                        borderRadius: 7,
                        border: '1px solid #e2ebe5',
                        background: 'transparent',
                        color: '#6b7f76',
                        fontSize: '0.78rem',
                        fontWeight: 500,
                        cursor: 'pointer',
                        fontFamily: 'inherit',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 6,
                        transition: 'all 0.12s ease',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = '#fff1f2'; e.currentTarget.style.color = '#be123c'; e.currentTarget.style.borderColor = '#fecdd3'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#6b7f76'; e.currentTarget.style.borderColor = '#e2ebe5'; }}
                >
                    <Icons.Logout />
                    Sign out
                </button>
            </div>
        </aside>
    );
}
