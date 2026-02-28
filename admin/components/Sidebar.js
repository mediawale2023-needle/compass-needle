'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';

const NAV_ITEMS = [
    { href: '/dashboard', label: 'Overview', icon: '📊' },
    { href: '/dashboard/profiles', label: 'Profile Editor', icon: '✏️' },
    { href: '/dashboard/geography', label: 'Geography Upload', icon: '🗺️' },
    { href: '/dashboard/rules', label: 'Geography Rules', icon: '📐' },
    { href: '/dashboard/intelligence', label: 'Case Intelligence', icon: '🔍' },
    { href: '/dashboard/settings', label: 'Settings', icon: '⚙️' },
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
            padding: '1.5rem 0',
            position: 'fixed',
            top: 0,
            left: 0,
            zIndex: 50,
        }}>
            {/* Logo */}
            <div style={{ padding: '0 1.2rem 1.5rem', borderBottom: '1px solid #e2ebe5' }}>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#006a4d', letterSpacing: '-0.5px' }}>
                    Needle
                </div>
                <div style={{ fontSize: '0.7rem', color: '#6b7f76', marginTop: 2, fontWeight: 500, letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                    Command Center
                </div>
            </div>

            {/* Nav */}
            <nav style={{ flex: 1, padding: '1rem 0.8rem' }}>
                {NAV_ITEMS.map((item) => {
                    const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 10,
                                padding: '10px 14px',
                                borderRadius: 10,
                                marginBottom: 4,
                                fontSize: '0.85rem',
                                fontWeight: isActive ? 600 : 500,
                                color: isActive ? '#006a4d' : '#6b7f76',
                                background: isActive ? 'rgba(0, 106, 77, 0.08)' : 'transparent',
                                textDecoration: 'none',
                                transition: 'all 0.15s ease',
                            }}
                        >
                            <span style={{ fontSize: '1rem' }}>{item.icon}</span>
                            {item.label}
                        </Link>
                    );
                })}
            </nav>

            {/* Footer */}
            <div style={{ padding: '1rem 1.2rem', borderTop: '1px solid #e2ebe5' }}>
                <div style={{ fontSize: '0.78rem', color: '#6b7f76', marginBottom: 8 }}>
                    Signed in as <strong style={{ color: '#1a2e28' }}>{user?.username || 'admin'}</strong>
                </div>
                <button
                    onClick={logout}
                    style={{
                        width: '100%',
                        padding: '8px 14px',
                        borderRadius: 8,
                        border: '1px solid #e2ebe5',
                        background: 'transparent',
                        color: '#6b7f76',
                        fontSize: '0.8rem',
                        fontWeight: 500,
                        cursor: 'pointer',
                        fontFamily: 'inherit',
                    }}
                >
                    Logout
                </button>
            </div>
        </aside>
    );
}
