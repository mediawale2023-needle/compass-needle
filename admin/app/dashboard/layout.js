'use client';
import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { AdminSignalsProvider } from '@/lib/admin-signals';
import Sidebar from '@/components/Sidebar';
import TopBar from '@/components/admin-ui/TopBar';

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

    // Escape closes the drawer; the page behind does not scroll while open.
    useEffect(() => {
        if (!navigationOpen) return undefined;
        const onKey = (event) => { if (event.key === 'Escape') setNavigationOpen(false); };
        document.addEventListener('keydown', onKey);
        const previous = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        return () => {
            document.removeEventListener('keydown', onKey);
            document.body.style.overflow = previous;
        };
    }, [navigationOpen]);

    if (loading) {
        return (
            <div className="nx-boot">
                <div className="nx-boot-mark" aria-hidden="true" />
                <p>Loading…</p>
            </div>
        );
    }
    if (!user) return null;

    return (
        <AdminSignalsProvider>
            <div className="nx-shell">
                <Sidebar open={navigationOpen} onClose={() => setNavigationOpen(false)} />
                <div className="nx-main">
                    <TopBar navigationOpen={navigationOpen} onOpenNavigation={() => setNavigationOpen(true)} />
                    <main className="nx-content" id="main-content">{children}</main>
                </div>
            </div>
        </AdminSignalsProvider>
    );
}
