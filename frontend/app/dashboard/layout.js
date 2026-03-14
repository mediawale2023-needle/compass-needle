'use client';

import { useAuth } from '@/lib/auth';
import { useRouter, usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import { apiGet } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { 
    Menu, 
    Clock, 
    Calendar,
    FileText,
    MessageSquare,
    FileEdit,
    Search,
    X,
    Loader2
} from 'lucide-react';

const TYPE_LABELS = {
    draft_letter: 'Letter',
    draft_question: 'PQ',
    analysis: 'Analysis',
    copilot_chat: 'Chat',
};

const TYPE_ICONS = {
    draft_letter: FileText,
    draft_question: FileEdit,
    analysis: Search,
    copilot_chat: MessageSquare,
};

export default function DashboardLayout({ children }) {
    const { user, logout, loading } = useAuth();
    const router = useRouter();
    const pathname = usePathname();
    const [showHistory, setShowHistory] = useState(false);
    const [history, setHistory] = useState([]);
    const [historyLoading, setHistoryLoading] = useState(false);
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const [badges, setBadges] = useState({});
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

    useEffect(() => {
        setIsMobileMenuOpen(false);
    }, [pathname]);

    useEffect(() => {
        if (!loading && !user) router.push('/');
    }, [user, loading, router]);

    useEffect(() => {
        if (!user) return;
        apiGet('/api/dashboard/summary')
            .then(data => {
                const statuses = data?.status_breakdown || {};
                const newCount = statuses['new'] || 0;
                setBadges({
                    letterbox: newCount,
                    briefcase: newCount,
                });
            })
            .catch(() => {});
    }, [user]);

    const openHistory = async () => {
        setShowHistory(true);
        setHistoryLoading(true);
        try {
            const data = await apiGet('/api/history?limit=30');
            setHistory(data.items || []);
        } catch { setHistory([]); }
        finally { setHistoryLoading(false); }
    };

    if (loading) return (
        <div className="min-h-screen flex items-center justify-center bg-background">
            <div className="flex flex-col items-center gap-3">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <span className="text-sm text-muted-foreground">Loading...</span>
            </div>
        </div>
    );
    
    if (!user) return null;

    return (
        <div className="min-h-screen bg-background">
            {/* Mobile Header */}
            <header className="md:hidden flex items-center justify-between bg-card border-b border-border px-4 h-14 sticky top-0 z-40">
                <div className="flex items-center gap-3">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-9 w-9"
                        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                    >
                        {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
                    </Button>
                    <span className="font-bold text-foreground">Compass Needle</span>
                </div>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9"
                    onClick={openHistory}
                >
                    <Clock className="h-5 w-5 text-muted-foreground" />
                </Button>
            </header>

            <Sidebar 
                user={user} 
                onLogout={() => { logout(); router.push('/'); }} 
                isOpen={isMobileMenuOpen} 
                setIsOpen={setIsMobileMenuOpen} 
                badges={badges}
                collapsed={sidebarCollapsed}
                setCollapsed={setSidebarCollapsed}
            />

            <main className={cn(
                "min-h-screen flex flex-col transition-all duration-300",
                sidebarCollapsed ? "md:ml-[72px]" : "md:ml-64"
            )}>
                {/* Desktop Header */}
                <header className="hidden md:flex items-center justify-between bg-card border-b border-border px-6 h-14 sticky top-0 z-30">
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2 text-sm">
                            <span className="font-semibold text-foreground">{user.display_name}</span>
                            <Separator orientation="vertical" className="h-4" />
                            <span className="text-muted-foreground">
                                {user.constituency} · {user.house}
                            </span>
                        </div>
                    </div>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Calendar className="h-3.5 w-3.5" />
                            {new Date().toLocaleDateString('en-IN', { 
                                weekday: 'long', 
                                day: 'numeric', 
                                month: 'long', 
                                year: 'numeric' 
                            })}
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-8 gap-2"
                            onClick={openHistory}
                        >
                            <Clock className="h-3.5 w-3.5" />
                            <span className="hidden lg:inline">Activity</span>
                        </Button>
                    </div>
                </header>

                {/* Content */}
                <div className="flex-1 p-4 md:p-6 animate-fade-in">
                    {children}
                </div>
            </main>

            {/* History Sheet */}
            <Sheet open={showHistory} onOpenChange={setShowHistory}>
                <SheetContent className="w-full sm:max-w-md p-0">
                    <SheetHeader className="px-6 py-4 border-b border-border">
                        <SheetTitle className="flex items-center justify-between">
                            <span>Activity History</span>
                            <span className="text-xs font-normal text-muted-foreground">
                                Last 30 days
                            </span>
                        </SheetTitle>
                    </SheetHeader>
                    
                    <ScrollArea className="h-[calc(100vh-140px)]">
                        {historyLoading ? (
                            <div className="flex items-center justify-center py-16">
                                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : history.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
                                <Clock className="h-12 w-12 text-muted-foreground/30 mb-4" />
                                <p className="text-sm text-muted-foreground">No activity yet</p>
                                <p className="text-xs text-muted-foreground/70 mt-1">
                                    Your recent actions will appear here
                                </p>
                            </div>
                        ) : (
                            <div className="divide-y divide-border">
                                {history.map(item => {
                                    const Icon = TYPE_ICONS[item.activity_type] || FileText;
                                    return (
                                        <button
                                            key={item.id}
                                            className="w-full px-6 py-4 hover:bg-accent/50 transition-colors text-left"
                                            onClick={() => { 
                                                setShowHistory(false); 
                                                router.push('/dashboard/archives'); 
                                            }}
                                        >
                                            <div className="flex items-start gap-3">
                                                <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                                                    <Icon className="h-4 w-4 text-primary" />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 mb-0.5">
                                                        <span className="text-xs font-semibold text-primary uppercase">
                                                            {TYPE_LABELS[item.activity_type] || item.activity_type}
                                                        </span>
                                                    </div>
                                                    <p className="text-sm font-medium text-foreground truncate">
                                                        {item.title}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground mt-0.5">
                                                        {item.created_at 
                                                            ? new Date(item.created_at).toLocaleString('en-IN', {
                                                                day: '2-digit', 
                                                                month: 'short', 
                                                                hour: '2-digit', 
                                                                minute: '2-digit'
                                                            }) 
                                                            : '–'}
                                                    </p>
                                                </div>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </ScrollArea>

                    <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-border bg-card">
                        <Button
                            className="w-full"
                            onClick={() => { 
                                setShowHistory(false); 
                                router.push('/dashboard/archives'); 
                            }}
                        >
                            View All in Archives
                        </Button>
                    </div>
                </SheetContent>
            </Sheet>
        </div>
    );
}
