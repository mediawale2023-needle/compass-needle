'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_ITEMS = [
    { name: 'Dashboard', path: '/dashboard' },
    { name: 'Letterbox', path: '/dashboard/letterbox' },
    { name: 'Briefcase', path: '/dashboard/sansadx' },
    { name: 'Research Desk', path: '/dashboard/copilot' },
    { name: 'Drafter', path: '/dashboard/drafter' },
    { name: 'Schemes', path: '/dashboard/schemes' },
    { name: 'CSR Intelligence', path: '/dashboard/csr' },
    { name: 'Archives', path: '/dashboard/archives' },
    { name: 'Settings', path: '/dashboard/settings' },
];

export default function Sidebar({ user, onLogout }) {
    const pathname = usePathname();
    const color = user?.theme_color || '#006a4d';
    const house = user?.house || 'Lok Sabha';

    return (
        <aside className="w-60 h-screen flex flex-col fixed left-0 top-0 z-30 bg-white border-r" style={{ borderColor: '#ddd' }}>
            {/* House Color Bar (matches sansad.in top accent) */}
            <div style={{ height: 4, background: color }} />

            {/* Logo */}
            <div className="px-5 py-4 border-b" style={{ borderColor: '#eee' }}>
                <div className="text-lg font-bold" style={{ color }}>Needle</div>
                <div className="text-[11px] text-gray-500 mt-0.5">{house}</div>
            </div>

            {/* MP Info */}
            <div className="px-5 py-3 border-b" style={{ borderColor: '#eee', background: '#fafafa' }}>
                <div className="text-sm font-semibold text-gray-800 truncate">{user?.display_name}</div>
                <div className="text-[11px] text-gray-500 truncate">{user?.constituency}</div>
            </div>

            {/* Nav */}
            <nav className="flex-1 py-2 overflow-y-auto">
                {NAV_ITEMS.map((item) => {
                    const active = pathname === item.path || (item.path !== '/dashboard' && pathname.startsWith(item.path));
                    return (
                        <Link
                            key={item.path}
                            href={item.path}
                            className="block px-5 py-2.5 text-[13px] font-medium transition-colors"
                            style={{
                                color: active ? 'white' : '#555',
                                background: active ? color : 'transparent',
                                borderLeft: active ? `3px solid ${color}` : '3px solid transparent',
                            }}
                        >
                            {item.name}
                        </Link>
                    );
                })}
            </nav>

            {/* Logout */}
            <div className="border-t px-5 py-3" style={{ borderColor: '#eee' }}>
                <button
                    onClick={onLogout}
                    className="text-[13px] font-medium text-gray-500 hover:text-red-600 transition-colors"
                >
                    Log Out
                </button>
            </div>
        </aside>
    );
}
