'use client';
import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import NotificationTray from '@/components/NotificationTray';

const PAGE_TITLES = {
    '/dashboard': { title: 'Overview', desc: 'Monitor platform readiness, account setup, and operational health from one control surface' },
    '/dashboard/accounts': { title: 'Accounts', desc: 'Manage account lifecycle, setup progress, linked staff, and launch readiness' },
    '/dashboard/seats': { title: 'Seats', desc: 'Review shared seat identity, tenant usage, and constituency readiness across geography and maps' },
    '/dashboard/shared-geography': { title: 'Shared Geography', desc: 'Manage seat-scoped geography datasets, inferred hierarchy, diagnostics, and routing rules' },
    '/dashboard/cases-intelligence': { title: 'Cases & Intelligence', desc: 'Operate case intelligence, knowledge coverage, AI tooling, and usage insight as one domain' },
    '/dashboard/staff-access': { title: 'Staff & Access', desc: 'Manage platform staff, administrative permissions, and access audit trails' },
    '/dashboard/system': { title: 'System', desc: 'Control platform-wide health, syncs, announcements, and administrative settings' },
    '/dashboard/seat-maps': { title: 'Seat Maps', desc: 'Manage shared constituency boundaries, generation workflows, and seat map readiness' },
    '/dashboard/constituency': { title: 'Constituency Intelligence', desc: 'Review constituency intelligence and legacy deep-dive reference material' },
};

export default function DashboardLayout({ children }) {
    const { user, loading } = useAuth();
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        if (!loading && !user) router.push('/');
    }, [user, loading, router]);

    if (loading) {
        return (
            <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                    <div style={{
                        width: 36, height: 36, borderRadius: 9,
                        background: 'linear-gradient(135deg, #006a4d, #00875f)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="12" y1="2" x2="12" y2="22"/>
                            <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                        </svg>
                    </div>
                    <div style={{ color: '#6b7f76', fontSize: '0.82rem' }}>Loading…</div>
                </div>
            </div>
        );
    }
    if (!user) return null;

    const meta = Object.entries(PAGE_TITLES).find(([route]) => pathname === route || (route !== '/dashboard' && pathname.startsWith(`${route}/`)))?.[1]
        || { title: 'Needle', desc: '' };

    return (
        <div style={{ display: 'flex', background: '#f4f6f5', minHeight: '100vh' }}>
            <Sidebar />
            <main style={{ marginLeft: 240, flex: 1, minHeight: '100vh', padding: '1.75rem 2rem' }}>
                {/* Page Header */}
                <div style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    marginBottom: '1.5rem',
                    paddingBottom: '1.25rem',
                    borderBottom: '1px solid #e2ebe5',
                }}>
                    <div>
                        <h1 style={{
                            fontSize: '1.25rem',
                            fontWeight: 700,
                            color: '#1a2e28',
                            margin: 0,
                            letterSpacing: '-0.4px',
                            lineHeight: 1.3,
                        }}>
                            {meta.title}
                        </h1>
                        {meta.desc && (
                            <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#6b7f76' }}>
                                {meta.desc}
                            </p>
                        )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0, marginTop: 2 }}>
                        <NotificationTray />
                        <div style={{
                            background: 'rgba(0, 106, 77, 0.08)',
                            color: '#006a4d',
                            padding: '5px 12px',
                            borderRadius: 20,
                            fontSize: '0.7rem',
                            fontWeight: 700,
                            letterSpacing: '0.8px',
                        }}>
                            ADMIN
                        </div>
                    </div>
                </div>

                {children}
            </main>
        </div>
    );
}
