'use client';
import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import NotificationTray from '@/components/NotificationTray';

const PAGE_TITLES = {
    '/dashboard': { title: 'Overview', desc: 'Manage MPs and platform configuration' },
    '/dashboard/profiles': { title: 'Profile Editor', desc: 'Edit MP identity, credentials, and AI profile data' },
    '/dashboard/geography': { title: 'Geography Upload', desc: 'Upload and manage polling station data from Election Commission PDFs' },
    '/dashboard/rules': { title: 'Geography Rules', desc: 'Define location-to-assembly-constituency override rules per MP' },
    '/dashboard/intelligence': { title: 'Case Intelligence', desc: 'Platform health, case explorer, and grievance analytics' },
    '/dashboard/health': { title: 'Tenant Health', desc: 'Monitor MP tenant activity status across the platform' },
    '/dashboard/analytics': { title: 'Usage Analytics', desc: 'Monthly activity per tenant — current calendar month' },
    '/dashboard/staff': { title: 'Staff Management', desc: 'Manage all non-admin staff accounts across tenants' },
    '/dashboard/announcements': { title: 'Announcements', desc: 'Compose banners shown on all MP dashboards' },
    '/dashboard/settings': { title: 'Settings', desc: 'Admin account and editor access management' },
    '/dashboard/mps/new': { title: 'Add New MP', desc: 'Create a new Member of Parliament account and profile' },
    '/dashboard/audit': { title: 'Audit Log', desc: 'Track all administrative actions across the platform' },
    '/dashboard/knowledge': { title: 'Knowledge Sync', desc: 'Unified control plane for constituency profiles, parliament records, answer coverage, and brain indexing' },
    '/dashboard/constituency': { title: 'Constituency Intelligence', desc: 'Deep political, demographic, economic and cultural profiles for each constituency' },
    '/dashboard/parliament-sync': { title: 'Parliament Sync', desc: 'Map subscribed MPs to their sansad.in member ID and manage 18th Lok Sabha data sync' },
    '/dashboard/brain': { title: 'Brain Playground', desc: 'Test semantic retrieval over memory_chunks — exactly what Copilot and Drafter see' },
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

    const meta = PAGE_TITLES[pathname] || { title: 'Needle', desc: '' };

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
