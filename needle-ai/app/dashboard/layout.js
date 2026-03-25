'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Menu, Loader2 } from 'lucide-react';

export default function DashboardLayout({ children }) {
    const { user, logout, loading } = useAuth();
    const router = useRouter();
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [collapsed, setCollapsed] = useState(false);
    const [badges, setBadges] = useState({});

    useEffect(() => {
        if (!loading && !user) router.replace('/');
    }, [user, loading, router]);

    // Fetch badge counts
    useEffect(() => {
        if (!user) return;
        const fetchBadges = async () => {
            try {
                const data = await apiGet('/api/dashboard/summary');
                const newCount = (data.by_status || []).find(s => s.status === 'new')?.count || 0;
                setBadges({ messages: newCount });
            } catch {
                // Silently fail — badges are non-critical
            }
        };
        fetchBadges();
        const interval = setInterval(fetchBadges, 60000); // refresh every 60s
        return () => clearInterval(interval);
    }, [user]);

    const handleLogout = () => {
        logout();
        router.replace('/');
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    if (!user) return null;

    return (
        <div className="min-h-screen bg-background">
            <Sidebar
                user={user}
                onLogout={handleLogout}
                isOpen={sidebarOpen}
                setIsOpen={setSidebarOpen}
                badges={badges}
                collapsed={collapsed}
                setCollapsed={setCollapsed}
            />

            {/* Main Content */}
            <main className={cn(
                "transition-all duration-300",
                collapsed ? "md:ml-[72px]" : "md:ml-64"
            )}>
                {/* Mobile Header */}
                <div className="md:hidden flex items-center h-14 px-4 border-b border-border bg-card sticky top-0 z-30">
                    <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(true)}>
                        <Menu className="h-5 w-5" />
                    </Button>
                    <span className="ml-3 font-semibold text-foreground">Ambassador</span>
                </div>

                <div className="p-4 md:p-6 max-w-7xl mx-auto">
                    {children}
                </div>
            </main>
        </div>
    );
}
