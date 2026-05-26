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
import {
    Bell,
    Calendar,
    Clock,
    FileEdit,
    FileText,
    Loader2,
    Menu,
    MessageSquare,
    Search,
    X,
} from 'lucide-react';

const TYPE_LABELS = {
    draft_letter: 'Letter',
    draft_question: 'Draft',
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
    const [announcements, setAnnouncements] = useState([]);
    const [dismissedIds, setDismissedIds] = useState([]);

    useEffect(() => {
        setIsMobileMenuOpen(false);
    }, [pathname]);

    useEffect(() => {
        if (!loading && !user) router.push('/');
    }, [user, loading, router]);

    useEffect(() => {
        if (!user) return;
        let cancelled = false;

        apiGet('/api/dashboard/summary')
            .then(data => {
                if (cancelled) return;
                const statuses = data?.status_breakdown || {};
                const newCount = statuses.new || 0;
                setBadges(b => ({ ...b, briefcase: newCount }));
            })
            .catch(() => {});

        try {
            const stored = JSON.parse(localStorage.getItem('dismissed_announcements') || '[]');
            setDismissedIds(stored);
        } catch {
            setDismissedIds([]);
        }

        const secondaryTimer = setTimeout(() => {
            apiGet('/api/letterbox?direction=inbox&status=new&limit=1&offset=0')
                .then(r => {
                    if (!cancelled) setBadges(b => ({ ...b, letterbox: r?.total || 0 }));
                })
                .catch(() => {});

            apiGet('/api/announcements/active')
                .then(d => {
                    if (!cancelled) setAnnouncements(d.announcements || []);
                })
                .catch(() => {});
        }, 900);

        return () => {
            cancelled = true;
            clearTimeout(secondaryTimer);
        };
    }, [user]);

    const dismissAnnouncement = (id) => {
        const next = [...dismissedIds, id];
        setDismissedIds(next);
        try {
            localStorage.setItem('dismissed_announcements', JSON.stringify(next));
        } catch {}
    };

    const visibleAnnouncements = announcements.filter(a => !dismissedIds.includes(a.id));

    const historyItemHref = (item) => {
        const meta = item?.metadata || {};
        if (typeof meta === 'string') return '/dashboard/archives';
        const direct = meta.href || meta.url || meta.path;
        if (typeof direct === 'string' && direct.startsWith('/')) return direct;

        if (item?.activity_type === 'draft_letter') {
            const draftId = meta.draft_id || meta.letter_id || meta.id;
            return draftId ? `/dashboard/drafter?mode=letter&draft_id=${encodeURIComponent(draftId)}` : '/dashboard/drafter?mode=letter';
        }
        if (item?.activity_type === 'draft_question') {
            return `/dashboard/archives?activity_id=${encodeURIComponent(item?.id || '')}`;
        }
        if (item?.activity_type === 'analysis' || item?.activity_type === 'copilot_chat') {
            const sessionId = meta.session_id || meta.chat_id || meta.id;
            return sessionId
                ? `/dashboard/sansadai?tab=research&session=${encodeURIComponent(sessionId)}`
                : '/dashboard/sansadai?tab=research';
        }
        return `/dashboard/archives?activity_id=${encodeURIComponent(item?.id || '')}`;
    };

    const openHistory = async () => {
        setShowHistory(true);
        setHistoryLoading(true);
        try {
            const data = await apiGet('/api/history?limit=30');
            setHistory(data.items || []);
        } catch {
            setHistory([]);
        } finally {
            setHistoryLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="dashboard-canvas flex min-h-screen items-center justify-center">
                <div className="dashboard-panel flex flex-col items-center gap-3 px-8 py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-[#0d6a4d]" />
                    <span className="text-sm text-[#4a453a]">Loading constituency workspace...</span>
                </div>
            </div>
        );
    }

    if (!user) return null;

    return (
        <div className="dashboard-canvas min-h-screen text-[#1a1812]">
            <header className="sticky top-0 z-40 border-b border-[var(--hairline)] bg-[rgba(251,246,231,0.96)] backdrop-blur md:hidden">
                <div className="flex h-1">
                    <div className="flex-1 bg-[#c76a1a]" />
                    <div className="flex-1 bg-[#f2ebd9]" />
                    <div className="flex-1 bg-[#0d6a4d]" />
                </div>
                <div className="flex items-center justify-between px-4 py-3">
                    <div className="flex items-center gap-3">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-10 w-10 rounded-none border border-[var(--hairline)] bg-white/40"
                            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                            aria-label={isMobileMenuOpen ? 'Close menu' : 'Open menu'}
                        >
                            {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
                        </Button>
                        <div>
                            <p className="font-editorial text-lg font-semibold text-[#1a1812]">Compass Needle</p>
                            <p className="font-mono-ui text-[10px] uppercase tracking-[0.18em] text-[#7a7263]">
                                Constituency Desk
                            </p>
                        </div>
                    </div>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-10 w-10 rounded-none border border-[var(--hairline)] bg-white/40"
                        onClick={openHistory}
                        aria-label="Open activity history"
                    >
                        <Clock className="h-5 w-5 text-[#4a453a]" />
                    </Button>
                </div>
            </header>

            <Sidebar
                user={user}
                onLogout={() => {
                    logout();
                    router.push('/');
                }}
                isOpen={isMobileMenuOpen}
                setIsOpen={setIsMobileMenuOpen}
                badges={badges}
                collapsed={sidebarCollapsed}
                setCollapsed={setSidebarCollapsed}
            />

            <main
                className={cn(
                    'min-h-screen transition-all duration-300',
                    sidebarCollapsed ? 'md:ml-[88px]' : 'md:ml-[280px]'
                )}
            >
                <header className="hidden border-b border-[var(--hairline)] bg-[rgba(251,246,231,0.92)] backdrop-blur md:block">
                    <div className="flex h-1">
                        <div className="flex-1 bg-[#c76a1a]" />
                        <div className="flex-1 bg-[#f2ebd9]" />
                        <div className="flex-1 bg-[#0d6a4d]" />
                    </div>
                    <div className="grid grid-cols-[1fr_auto] items-center gap-6 px-6 py-4">
                        <div>
                            <div className="flex items-center gap-3">
                                <h1 className="font-editorial text-[1.65rem] font-semibold tracking-[-0.02em] text-[#1a1812]">
                                    Operations Dashboard
                                </h1>
                                <span className="font-mono-ui dashboard-pill px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em]">
                                    Live
                                </span>
                            </div>
                            <p className="font-mono-ui mt-1 text-[11px] uppercase tracking-[0.18em] text-[#7a7263]">
                                {user.constituency} · {user.house} · {new Date().toLocaleDateString('en-IN', {
                                    weekday: 'long',
                                    day: 'numeric',
                                    month: 'long',
                                    year: 'numeric',
                                })}
                            </p>
                        </div>

                        <div className="flex items-center gap-3">
                            <div className="dashboard-panel flex items-center gap-3 px-4 py-2 text-sm">
                                <Calendar className="h-4 w-4 text-[#0d6a4d]" />
                                <div>
                                    <p className="font-medium text-[#1a1812]">{user.display_name}</p>
                                    <p className="text-xs text-[#7a7263]">Office of the MP</p>
                                </div>
                            </div>
                            <Button
                                variant="outline"
                                size="sm"
                                className="h-10 rounded-none border-[var(--hairline-strong)] bg-transparent px-4 text-[#1a1812] hover:bg-[#efe6d2]"
                                onClick={openHistory}
                            >
                                <Clock className="mr-2 h-4 w-4" />
                                Activity
                            </Button>
                        </div>
                    </div>
                </header>

                {visibleAnnouncements.length > 0 && (
                    <div className="space-y-3 px-4 pt-4 md:px-6">
                        {visibleAnnouncements.map(a => (
                            <div
                                key={a.id}
                                className="dashboard-panel flex items-start gap-3 rounded-none border-l-4 border-l-[#c76a1a] px-4 py-3"
                            >
                                <Bell className="mt-0.5 h-4 w-4 shrink-0 text-[#0d6a4d]" />
                                <div className="min-w-0 flex-1">
                                    <p className="font-medium text-[#1a1812]">{a.title}</p>
                                    {a.body && (
                                        <p className="mt-1 text-sm text-[#4a453a]">{a.body}</p>
                                    )}
                                </div>
                                <button
                                    onClick={() => dismissAnnouncement(a.id)}
                                    className="text-[#7a7263] transition-colors hover:text-[#1a1812]"
                                    aria-label="Dismiss"
                                >
                                    <X className="h-4 w-4" />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                <div className="px-4 py-5 md:px-6 md:py-6">
                    {children}
                </div>
            </main>

            <Sheet open={showHistory} onOpenChange={setShowHistory}>
                <SheetContent className="w-full max-w-none rounded-none border-l border-[var(--hairline)] bg-[#fbf6e7] p-0 sm:max-w-md">
                    <SheetHeader className="border-b border-[var(--hairline)] px-6 py-4">
                        <SheetTitle className="flex items-center justify-between">
                            <span className="font-editorial text-2xl font-semibold">Activity Ledger</span>
                            <span className="font-mono-ui text-[11px] font-normal uppercase tracking-[0.18em] text-[#7a7263]">
                                Last 30 days
                            </span>
                        </SheetTitle>
                    </SheetHeader>

                    <ScrollArea className="h-full">
                        <div className="px-6 py-5">
                            {historyLoading ? (
                                <div className="flex items-center gap-3 py-6 text-sm text-[#4a453a]">
                                    <Loader2 className="h-4 w-4 animate-spin text-[#0d6a4d]" />
                                    Loading recent activity...
                                </div>
                            ) : history.length === 0 ? (
                                <div className="dashboard-panel rounded-none px-4 py-5 text-sm text-[#4a453a]">
                                    No recent activity found.
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {history.map(item => {
                                        const Icon = TYPE_ICONS[item.activity_type] || Clock;
                                        return (
                                            <button
                                                key={item.id}
                                                className="dashboard-panel flex w-full items-start gap-3 rounded-none px-4 py-4 text-left transition-transform duration-200 hover:-translate-y-0.5"
                                                onClick={() => {
                                                    setShowHistory(false);
                                                    router.push(historyItemHref(item));
                                                }}
                                            >
                                                <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-none bg-[#efe6d2] text-[#0d6a4d]">
                                                    <Icon className="h-4 w-4" />
                                                </div>
                                                <div className="min-w-0 flex-1">
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-medium text-[#1a1812]">
                                                            {TYPE_LABELS[item.activity_type] || 'Activity'}
                                                        </span>
                                                        <span className="font-mono-ui text-[10px] uppercase tracking-[0.16em] text-[#7a7263]">
                                                            {new Date(item.created_at).toLocaleDateString('en-IN')}
                                                        </span>
                                                    </div>
                                                    <p className="mt-1 text-sm text-[#4a453a]">
                                                        {item.title || item.summary || 'Open archived item'}
                                                    </p>
                                                </div>
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </ScrollArea>
                </SheetContent>
            </Sheet>
        </div>
    );
}
