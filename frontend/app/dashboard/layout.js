'use client';

import { useAuth } from '@/lib/auth';
import { useRouter, usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import Image from 'next/image';
import Sidebar from '@/components/Sidebar';
import { apiGet, apiPost } from '@/lib/api';
import { canAccessSansadAI, getAccountLabel, getSeatBadge } from '@/lib/account';
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
    const [supportInbox, setSupportInbox] = useState({ pending_requests: [], active_sessions: [] });
    const [supportBusyKey, setSupportBusyKey] = useState('');
    const isBriefcaseRoute = pathname?.startsWith('/dashboard/sansadx');

    useEffect(() => { setIsMobileMenuOpen(false); }, [pathname]);

    useEffect(() => {
        if (!loading && !user) router.push('/');
    }, [user, loading, router]);

    useEffect(() => {
        if (!loading && user?.must_change_password) {
            router.replace('/force-password-reset');
        }
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

    useEffect(() => {
        if (!user?.is_primary_account) {
            setSupportInbox({ pending_requests: [], active_sessions: [] });
            return;
        }
        let cancelled = false;

        const load = () => {
            apiGet('/api/support-access/inbox')
                .then((data) => {
                    if (!cancelled) {
                        setSupportInbox({
                            pending_requests: data?.pending_requests || [],
                            active_sessions: data?.active_sessions || [],
                        });
                    }
                })
                .catch(() => {});
        };

        load();
        const intervalId = window.setInterval(load, 15000);
        return () => {
            cancelled = true;
            window.clearInterval(intervalId);
        };
    }, [user?.is_primary_account]);

    const dismissAnnouncement = (id) => {
        const next = [...dismissedIds, id];
        setDismissedIds(next);
        try { localStorage.setItem('dismissed_announcements', JSON.stringify(next)); } catch {}
    };

    const visibleAnnouncements = announcements.filter(a => !dismissedIds.includes(a.id));
    const userRoleLabel = getAccountLabel(user);

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

    const refreshSupportInbox = async () => {
        if (!user?.is_primary_account) return;
        try {
            const data = await apiGet('/api/support-access/inbox');
            setSupportInbox({
                pending_requests: data?.pending_requests || [],
                active_sessions: data?.active_sessions || [],
            });
        } catch {}
    };

    const respondToSupportRequest = async (requestKey, action) => {
        setSupportBusyKey(`${action}:${requestKey}`);
        try {
            await apiPost(`/api/support-access/${requestKey}/${action}`, {});
            await refreshSupportInbox();
        } catch {
        } finally {
            setSupportBusyKey('');
        }
    };

    const revokeSupportSession = async (requestKey) => {
        setSupportBusyKey(`revoke:${requestKey}`);
        try {
            await apiPost(`/api/support-access/${requestKey}/revoke`, {});
            await refreshSupportInbox();
        } catch {
        } finally {
            setSupportBusyKey('');
        }
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

    if (!user || user.must_change_password) return null;

    const today = new Date().toLocaleDateString('en-IN', {
        weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    });

    return (
        <div className="min-h-screen" style={{ background: 'var(--cn-paper)' }}>
            {/* ── Mobile Header (shown on all routes so nav stays reachable) ── */}
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
                    <div className="flex items-center gap-2 min-w-0">
                        <Image
                            src="/needle-logo-cream.svg"
                            alt="Compass Needle"
                            width={32}
                            height={19}
                            className="h-[19px] w-auto shrink-0"
                        />
                        <span
                            className="font-semibold text-sm truncate"
                            style={{ fontFamily: '"Source Serif 4", serif', color: 'var(--cn-ink)' }}
                        >
                            Compass Needle
                        </span>
                    </div>
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
                onLogout={async () => { await logout(); router.push('/'); }}
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
                {!isBriefcaseRoute && (
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
                        {canAccessSansadAI(user) && (
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
                        )}

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
                                {user?.display_name?.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase() || 'CN'}
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
                                    {userRoleLabel}
                                    {user ? ` · ${getSeatBadge(user)}` : ''}
                                </div>
                            </div>
                        </div>
                    </header>
                )}

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

                {user?.is_support_access_session && (
                    <div className="px-4 md:px-6 pt-4">
                        <div
                            className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between px-4 py-3"
                            style={{
                                background: '#fff4dc',
                                border: '1px solid rgba(199,106,26,0.35)',
                            }}
                        >
                            <div>
                                <div style={{ fontSize: '0.72rem', letterSpacing: '0.12em', textTransform: 'uppercase', color: '#9a5b12', fontWeight: 700 }}>
                                    Admin Support Session
                                </div>
                                <div style={{ marginTop: 4, color: '#5f4317', fontSize: '0.86rem', lineHeight: 1.5 }}>
                                    Viewing this tenant with approved support access.
                                    {user?.support_access_requested_by ? ` Requested by ${user.support_access_requested_by}.` : ''}
                                    {user?.support_access_expires_at ? ` Expires ${new Date(user.support_access_expires_at).toLocaleString('en-IN')}.` : ''}
                                </div>
                            </div>
                            <button
                                className="btn-secondary"
                                style={{ fontSize: '0.78rem', padding: '7px 14px', alignSelf: 'flex-start' }}
                                onClick={async () => {
                                    await logout();
                                    router.push('/');
                                }}
                            >
                                End support session
                            </button>
                        </div>
                    </div>
                )}

                {!user?.is_support_access_session && user?.is_primary_account && supportInbox.pending_requests.length > 0 && (
                    <div className="px-4 md:px-6 pt-4 space-y-2">
                        {supportInbox.pending_requests.map((request) => (
                            <div
                                key={request.request_key}
                                className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between px-4 py-3"
                                style={{
                                    background: '#eef8f1',
                                    border: '1px solid rgba(0,106,77,0.24)',
                                }}
                            >
                                <div>
                                    <div style={{ fontSize: '0.72rem', letterSpacing: '0.12em', textTransform: 'uppercase', color: '#006a4d', fontWeight: 700 }}>
                                        Admin access approval requested
                                    </div>
                                    <div style={{ marginTop: 4, color: '#1a2e28', fontSize: '0.86rem', lineHeight: 1.5 }}>
                                        {request.requested_by_admin_username} wants to view this workspace for {request.duration_minutes || 30} minutes.
                                        {request.reason ? ` Reason: ${request.reason}` : ''}
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <button
                                        className="btn-secondary"
                                        style={{ fontSize: '0.78rem', padding: '7px 14px' }}
                                        disabled={supportBusyKey === `reject:${request.request_key}`}
                                        onClick={() => respondToSupportRequest(request.request_key, 'reject')}
                                    >
                                        Reject
                                    </button>
                                    <button
                                        className="btn-primary"
                                        style={{ fontSize: '0.78rem', padding: '7px 14px' }}
                                        disabled={supportBusyKey === `approve:${request.request_key}`}
                                        onClick={() => respondToSupportRequest(request.request_key, 'approve')}
                                    >
                                        {supportBusyKey === `approve:${request.request_key}` ? 'Approving…' : 'Approve'}
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {!user?.is_support_access_session && user?.is_primary_account && supportInbox.active_sessions.length > 0 && (
                    <div className="px-4 md:px-6 pt-4 space-y-2">
                        {supportInbox.active_sessions.map((request) => (
                            <div
                                key={request.request_key}
                                className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between px-4 py-3"
                                style={{
                                    background: '#f6f7f8',
                                    border: '1px solid rgba(26,46,40,0.12)',
                                }}
                            >
                                <div>
                                    <div style={{ fontSize: '0.72rem', letterSpacing: '0.12em', textTransform: 'uppercase', color: '#4a5f58', fontWeight: 700 }}>
                                        Active admin support session
                                    </div>
                                    <div style={{ marginTop: 4, color: '#1a2e28', fontSize: '0.86rem', lineHeight: 1.5 }}>
                                        {request.requested_by_admin_username} is currently viewing this workspace.
                                        {request.session_expires_at ? ` Session ends ${new Date(request.session_expires_at).toLocaleString('en-IN')}.` : ''}
                                    </div>
                                </div>
                                <button
                                    className="btn-secondary"
                                    style={{ fontSize: '0.78rem', padding: '7px 14px', alignSelf: 'flex-start' }}
                                    disabled={supportBusyKey === `revoke:${request.request_key}`}
                                    onClick={() => revokeSupportSession(request.request_key)}
                                >
                                    {supportBusyKey === `revoke:${request.request_key}` ? 'Revoking…' : 'End access'}
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                {/* Content */}
                <div className="flex-1 p-[14px] md:p-[14px] animate-fade-in">
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
