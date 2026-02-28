'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';

export default function DashboardLayout({ children }) {
    const { user, loading } = useAuth();
    const router = useRouter();

    useEffect(() => {
        if (!loading && !user) router.push('/');
    }, [user, loading, router]);

    if (loading) return <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7f76' }}>Loading...</div>;
    if (!user) return null;

    return (
        <div style={{ display: 'flex' }}>
            <Sidebar />
            <main style={{ marginLeft: 240, flex: 1, minHeight: '100vh', padding: '2rem' }}>
                {/* Header */}
                <div style={{
                    background: 'linear-gradient(135deg, #006a4d 0%, #00875f 50%, #006a4d 100%)',
                    borderRadius: 16,
                    padding: '1.8rem 2rem',
                    marginBottom: '1.5rem',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    boxShadow: '0 4px 20px rgba(0, 106, 77, 0.15)',
                }}>
                    <div>
                        <h1 style={{ color: '#ffffff', fontSize: '1.6rem', fontWeight: 700, margin: 0, letterSpacing: '-0.5px' }}>
                            Needle Command Center
                        </h1>
                        <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: '0.85rem', marginTop: 4 }}>
                            Multi-tenant MP management, geography, and system configuration
                        </div>
                    </div>
                    <div style={{
                        background: 'rgba(255,255,255,0.2)',
                        color: '#ffffff',
                        padding: '6px 14px',
                        borderRadius: 20,
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        letterSpacing: '0.5px',
                    }}>
                        ADMIN
                    </div>
                </div>

                {children}
            </main>
        </div>
    );
}
