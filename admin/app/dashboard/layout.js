'use client';
import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Menu } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import NotificationTray from '@/components/NotificationTray';

// Fallback titles for pages that do not yet render their own
// AdminPageHeader. When a page does supply one, CSS hides this
// (`.admin-main:has(.admin-page-header) .admin-shell-title`) so a page can
// never show two titles — the duplicate "Command Centre" heading came from
// the layout and the page each rendering one. This map shrinks to nothing as
// pages are migrated, and then this block can be deleted.
const PAGE_TITLES = {
    '/dashboard': 'Command Centre',
    '/dashboard/accounts': 'Accounts',
    '/dashboard/seats': 'Seats & Geography',
    '/dashboard/shared-geography': 'Shared Geography',
    '/dashboard/cases-intelligence': 'Case Operations',
    '/dashboard/staff-access': 'Administration',
    '/dashboard/system': 'Platform Operations',
    '/dashboard/seat-maps': 'Seat Maps',
    '/dashboard/constituency': 'Constituency Intelligence',
};

export default function DashboardLayout({ children }) {
    const { user, loading } = useAuth();
    const router = useRouter();
    const pathname = usePathname();
    const [navigationOpen, setNavigationOpen] = useState(false);

    useEffect(() => {
        if (!loading && !user) router.push('/');
    }, [user, loading, router]);

    // Close the mobile drawer on navigation so it never persists over content.
    useEffect(() => { setNavigationOpen(false); }, [pathname]);

    if (loading) {
        return (
            <div className="admin-boot">
                <div className="admin-boot-mark" aria-hidden="true" />
                <p>Loading…</p>
            </div>
        );
    }
    if (!user) return null;

    const title = Object.entries(PAGE_TITLES).find(
        ([route]) => pathname === route || (route !== '/dashboard' && pathname.startsWith(`${route}/`)),
    )?.[1] || 'Needle';

    return (
        <div className="admin-shell">
            <Sidebar open={navigationOpen} onClose={() => setNavigationOpen(false)} />
            <main className="admin-main">
                <div className="admin-header">
                    <button
                        type="button"
                        className="admin-mobile-nav-button"
                        aria-label="Open navigation"
                        aria-expanded={navigationOpen}
                        onClick={() => setNavigationOpen(true)}
                    >
                        <Menu size={16} strokeWidth={1.5} aria-hidden="true" />
                    </button>
                    <span className="admin-shell-title">{title}</span>
                    <span className="admin-header-spacer" />
                    <NotificationTray />
                    <span className="admin-env">Admin</span>
                </div>

                <div className="admin-content">{children}</div>
            </main>
        </div>
    );
}
