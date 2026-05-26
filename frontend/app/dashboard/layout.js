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
    Menu,
    Clock,
    FileText,
    MessageSquare,
    FileEdit,
    Search,
    X,
    Loader2,
    Bell,
    Sparkles,
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

    useEffect(() => { setIsMobileMenuOpen(false); }, [pathname]);

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
                setBadges(b => ({ ...b, briefcase: statuses['new'] || 0 }));
            })
            .catch(() => {});

        try {
            const stored = JSON.parse(localStorage.getItem('dismissed_announcements') || '[]');
            setDismissedIds(stored);
        } catch { setDismissedIds([]); }

        const timer = setTimeout(() => {
            apiGet('/api/letterbox?direction=inbox&status=new&limit=1&offset=0')
                .then(r => { if (!cancelled) setBadges(b => ({ ...b, letterbox: r?.total || 0 })); })
                .catch(() => {});
            apiGet('/api/announcements/active')
                .then(d => { if (!cancelled) setAnnouncements(d.announcements || []); })
                .catch(() => {});
        }, 900);

        return () => { cancelled = true; clearTimeout(timer); };
    }, [user]);

    const dismissAnnouncement = (id) => {
        const next = [...dismissedIds, id];
        setDismissedIds(next);
        try { localStorage.setItem('dismissed_announcements', JSON.stringify(next)); } catch {}
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
        } catch { setHistory([]); }
        finally { setHistoryLoading(false); }
    };

    if (loading) return (
        <div className="min-h-screen flex items-center justify-center" style={{ background: '#F2EBD9' }}>
            <div className="flex flex-col items-center gap-3">
                <Loader2 className="h-8 w-8 animate-spin" style={{ color: '#006A4D' }} />
                <span
                    className="text-sm tracking-[0.12em] uppercase"
                    style={{ color: '#7A7263', fontFamily: '"JetBrains Mono", monospace' }}
                >
                    Loading…
                </span>
            </div>
        </div>
    );

    if (!user) return null;

    const today = new Date().toLocaleDateString('en-IN', {
        weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    });

    return (
        <div className="min-h-screen" style={{ background: 'var(--cn-paper)' }}>
            {/* ── Mobile Header ── */}
            <header
                className="md:hidden flex items-center justify-between px-4 h-14 sticky top-0 z-40"
                style={{
                    background: 'var(--cn-paper)',
                    borderBottom: '1px solid var(--cn-hair)',
                }}
            >
                <div className="flex items-center gap-3">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-9 w-9"
                        style={{ color: 'var(--cn-ink)' }}
                        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                    >
                        {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
                    </Button>
                    <span
                        className="font-semibold text-sm"
                        style={{ fontFamily: '"Source Serif 4", serif', color: 'var(--cn-ink)' }}
                    >
                        Compass Needle
                    </span>
                </div>
                <button
                    className="h-9 w-9 flex items-center justify-center"
                    style={{ color: 'var(--cn-ink3)' }}
                    onClick={openHistory}
                >
                    <Clock className="h-5 w-5" />
                </button>
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
                'min-h-screen flex flex-col transition-all duration-300',
                sidebarCollapsed ? 'md:ml-[60px]' : 'md:ml-[220px]',
            )}>
                {/* ── Desktop Header ── */}
                <header
                    className="hidden md:grid sticky top-0 z-30"
                    style={{
                        background: 'var(--cn-paper)',
                        borderBottom: '1px solid var(--cn-hair)',
                        gridTemplateColumns: 'auto 1fr auto auto auto auto',
                        alignItems: 'center',
                        gap: '18px',
                        padding: '12px 24px',
                    }}
                >
                    {/* Title */}
                    <div>
                        <div className="flex items-center gap-2.5">
                            <span
                                className="font-semibold tracking-tight"
                                style={{
                                    fontFamily: '"Source Serif 4", serif',
                                    fontSize: '18px',
                                    color: 'var(--cn-ink)',
                                    letterSpacing: '-0.01em',
                                }}
                            >
                                Operations Dashboard
                            </span>
                            <span
                                className="px-1.5 py-0.5 text-[9.5px] font-bold tracking-[0.12em] uppercase"
                                style={{
                                    background: 'var(--cn-green-tint)',
                                    color: 'var(--cn-green-ink)',
                                }}
                            >
                                Live
                            </span>
                        </div>
                        <div
                            className="mt-0.5 text-[10px] tracking-[0.12em] uppercase"
                            style={{
                                fontFamily: '"JetBrains Mono", monospace',
                                color: 'var(--cn-ink3)',
                            }}
                        >
                            {user?.constituency} · {user?.house} · {today}
                        </div>
                    </div>

                    {/* Search bar */}
                    <div
                        className="flex items-center gap-2 px-3 py-2 w-full max-w-sm justify-self-center"
                        style={{
                            background: 'var(--cn-surface)',
                            border: '1px solid var(--cn-hair)',
                        }}
                    >
                        <Search className="h-3.5 w-3.5 shrink-0" style={{ color: 'var(--cn-ink3)' }} />
                        <input
                            placeholder="Search grievance ref, citizen ID, letter ref…"
                            className="flex-1 bg-transparent outline-none text-[12.5px]"
                            style={{ color: 'var(--cn-ink)', fontFamily: 'inherit' }}
                        />
                        <span
                            className="text-[10px] px-1 py-0.5 border"
                            style={{
                                fontFamily: '"JetBrains Mono", monospace',
                                color: 'var(--cn-ink3)',
                                borderColor: 'var(--cn-hair)',
                            }}
                        >
                            ⌘K
                        </span>
                    </div>

                    {/* Sansad AI button */}
                    <button
                        className="flex items-center gap-1.5 px-3 py-2 text-[11px] font-bold tracking-[0.08em] uppercase transition-opacity hover:opacity-90"
                        style={{
                            background: 'var(--cn-green)',
                            color: '#F5EFE0',
                            fontFamily: 'inherit',
                        }}
                        onClick={() => router.push('/dashboard/sansadai')}
                    >
                        <Sparkles className="h-3 w-3" />
                        Sansad AI
                    </button>

                    {/* Bell */}
                    <button
                        className="relative h-[34px] w-[34px] flex items-center justify-center"
                        style={{
                            background: 'var(--cn-surface)',
                            border: '1px solid var(--cn-hair)',
                            color: 'var(--cn-ink)',
                        }}
                        onClick={openHistory}
                    >
                        <Bell className="h-[14px] w-[14px]" />
                        {(badges.briefcase > 0 || badges.letterbox > 0) && (
                            <span
                                className="absolute top-[3px] right-[3px] text-[8px] font-bold px-[3px] leading-5 min-w-[14px] text-center"
                                style={{
                                    background: 'var(--cn-saffron)',
                                    color: '#fff',
                                    fontFamily: '"JetBrains Mono", monospace',
                                }}
                            >
                                {(badges.briefcase || 0) + (badges.letterbox || 0)}
                            </span>
                        )}
                    </button>

                    {/* User */}
                    <div className="flex items-center gap-2.5">
                        <div
                            className="h-[34px] w-[34px] flex items-center justify-center text-[13px] font-semibold shrink-0"
                            style={{
                                background: 'var(--cn-green)',
                                color: '#F5EFE0',
                                fontFamily: '"Source Serif 4", serif',
                            }}
                        >
                            {user?.display_name?.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase() || 'MP'}
                        </div>
                        <div>
                            <div
                                className="text-[12.5px] font-semibold leading-none"
                                style={{ color: 'var(--cn-ink)' }}
                            >
                                {user?.display_name}
                            </div>
                            <div
                                className="text-[10px] mt-0.5 tracking-[0.08em]"
                                style={{
                                    color: 'var(--cn-ink3)',
                                    fontFamily: '"JetBrains Mono", monospace',
                                }}
                            >
                                {user?.role === 'mp' ? 'MP' : user?.role === 'admin' ? 'Admin' : 'Staff'}
                                {user?.house?.includes('Lok') ? ' · LS' : ' · RS'}
                            </div>
                        </div>
                    </div>
                </header>

                {/* Announcements */}
                {visibleAnnouncements.length > 0 && (
                    <div className="px-4 md:px-6 pt-4 space-y-2">
                        {visibleAnnouncements.map(a => (
                            <div
                                key={a.id}
                                className="flex items-start gap-3 px-4 py-3"
                                style={{
                                    background: 'var(--cn-saffron-tint)',
                                    border: '1px solid rgba(199,106,26,0.3)',
                                }}
                            >
                                <Bell className="h-4 w-4 shrink-0 mt-0.5" style={{ color: 'var(--cn-saffron)' }} />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-semibold" style={{ color: 'var(--cn-ink)' }}>{a.title}</p>
                                    {a.body && <p className="text-xs mt-0.5" style={{ color: 'var(--cn-ink2)' }}>{a.body}</p>}
                                </div>
                                <button
                                    onClick={() => dismissAnnouncement(a.id)}
                                    className="shrink-0 opacity-60 hover:opacity-100 transition-opacity"
                                    style={{ color: 'var(--cn-ink2)' }}
                                >
                                    <X className="h-4 w-4" />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                {/* Content */}
                <div className="flex-1 p-3 sm:p-4 md:p-[14px] animate-fade-in overflow-x-hidden">
                    {children}
                </div>
            </main>

            {/* Activity History Sheet */}
            <Sheet open={showHistory} onOpenChange={setShowHistory}>
                <SheetContent className="w-full sm:max-w-md p-0" style={{ background: 'var(--cn-surface)' }}>
                    <SheetHeader
                        className="px-6 py-4"
                        style={{ borderBottom: '1px solid var(--cn-hair)' }}
                    >
                        <SheetTitle
                            className="flex items-center justify-between"
                            style={{ fontFamily: '"Source Serif 4", serif', color: 'var(--cn-ink)' }}
                        >
                            <span>Activity History</span>
                            <span
                                className="text-[10px] font-normal tracking-[0.12em] uppercase"
                                style={{ color: 'var(--cn-ink3)', fontFamily: '"JetBrains Mono", monospace' }}
                            >
                                Last 30 days
                            </span>
                        </SheetTitle>
                    </SheetHeader>

                    <ScrollArea className="h-[calc(100vh-140px)]">
                        {historyLoading ? (
                            <div className="flex items-center justify-center py-16">
                                <Loader2 className="h-6 w-6 animate-spin" style={{ color: 'var(--cn-ink3)' }} />
                            </div>
                        ) : history.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
                                <Clock className="h-12 w-12 mb-4" style={{ color: 'var(--cn-hair-strong)' }} />
                                <p className="text-sm" style={{ color: 'var(--cn-ink3)' }}>No activity yet</p>
                            </div>
                        ) : (
                            <div style={{ borderBottom: '1px solid var(--cn-hair)' }}>
                                {history.map(item => {
                                    const Icon = TYPE_ICONS[item.activity_type] || FileText;
                                    return (
                                        <button
                                            key={item.id}
                                            className="w-full px-6 py-4 hover:opacity-80 transition-opacity text-left"
                                            style={{ borderBottom: '1px solid var(--cn-hair)' }}
                                            onClick={() => { setShowHistory(false); router.push(historyItemHref(item)); }}
                                        >
                                            <div className="flex items-start gap-3">
                                                <div
                                                    className="h-8 w-8 flex items-center justify-center shrink-0"
                                                    style={{ background: 'var(--cn-green-tint)' }}
                                                >
                                                    <Icon className="h-4 w-4" style={{ color: 'var(--cn-green)' }} />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div
                                                        className="text-[10px] font-bold uppercase tracking-[0.1em] mb-0.5"
                                                        style={{ color: 'var(--cn-green)', fontFamily: '"JetBrains Mono", monospace' }}
                                                    >
                                                        {TYPE_LABELS[item.activity_type] || item.activity_type}
                                                    </div>
                                                    <p className="text-sm font-medium truncate" style={{ color: 'var(--cn-ink)' }}>
                                                        {item.title}
                                                    </p>
                                                    <p
                                                        className="text-xs mt-0.5"
                                                        style={{ color: 'var(--cn-ink3)', fontFamily: '"JetBrains Mono", monospace' }}
                                                    >
                                                        {item.created_at
                                                            ? new Date(item.created_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
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

                    <div
                        className="absolute bottom-0 left-0 right-0 p-4"
                        style={{ borderTop: '1px solid var(--cn-hair)', background: 'var(--cn-surface)' }}
                    >
                        <button
                            className="w-full py-2.5 text-[11px] font-bold tracking-[0.08em] uppercase transition-opacity hover:opacity-90"
                            style={{ background: 'var(--cn-green)', color: '#F5EFE0', fontFamily: 'inherit' }}
                            onClick={() => { setShowHistory(false); router.push('/dashboard/archives'); }}
                        >
                            View All in Archives
                        </button>
                    </div>
                </SheetContent>
            </Sheet>
        </div>
    );
}
