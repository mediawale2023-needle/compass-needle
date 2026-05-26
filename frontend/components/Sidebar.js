'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
    Archive,
    Bot,
    Briefcase,
    ChevronLeft,
    ChevronRight,
    Compass,
    LayoutDashboard,
    LogOut,
    Mail,
    PenTool,
    Settings,
    Users,
} from 'lucide-react';

const NAV_ITEMS = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Letterbox', path: '/dashboard/letterbox', icon: Mail, badgeKey: 'letterbox' },
    { name: 'Briefcase', path: '/dashboard/sansadx', icon: Briefcase, badgeKey: 'briefcase' },
    { name: 'Drafter', path: '/dashboard/drafter', icon: PenTool },
    { name: 'SansadAI', path: '/dashboard/sansadai', icon: Bot, mpOnly: true },
    { name: 'Convergence', path: '/dashboard/csr', icon: Users, mpOnly: true },
    { name: 'Archives', path: '/dashboard/archives', icon: Archive },
    { name: 'Settings', path: '/dashboard/settings', icon: Settings },
];

function NavBadge({ count, highlighted = false }) {
    if (!count || count < 1) return null;
    return (
        <Badge
            className={cn(
                'h-5 min-w-5 rounded-none border-0 px-1.5 text-[10px] font-semibold shadow-none',
                highlighted
                    ? 'bg-[#c76a1a] text-[#fbf6e7]'
                    : 'bg-[#efe4cb] text-[#0b3b2e]'
            )}
        >
            {count > 99 ? '99+' : count}
        </Badge>
    );
}

export default function Sidebar({
    user,
    onLogout,
    isOpen,
    setIsOpen,
    badges = {},
    collapsed = false,
    setCollapsed,
}) {
    const pathname = usePathname();
    const house = user?.house || 'Lok Sabha';

    return (
        <>
            <div
                className={cn(
                    'fixed inset-0 z-40 bg-[#1a1812]/30 backdrop-blur-sm transition-opacity duration-300 md:hidden',
                    isOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
                )}
                onClick={() => setIsOpen?.(false)}
            />

            <aside
                className={cn(
                    'fixed left-0 top-0 z-50 flex h-screen flex-col overflow-hidden border-r border-white/10 bg-[#083728] text-[#f2ebd9] transition-all duration-300 ease-out',
                    'shadow-[0_24px_60px_rgba(8,55,40,0.32)] md:translate-x-0',
                    isOpen ? 'translate-x-0' : '-translate-x-full',
                    collapsed ? 'md:w-[88px]' : 'md:w-[280px]',
                    'w-[292px]'
                )}
            >
                <div className="flex h-1">
                    <div className="flex-1 bg-[#c76a1a]" />
                    <div className="flex-1 bg-[#f2ebd9]" />
                    <div className="flex-1 bg-[#0d6a4d]" />
                </div>

                <div className={cn('border-b border-white/10 px-4 py-5', collapsed && 'md:px-3')}>
                    <div className={cn('flex items-center gap-3', collapsed && 'md:justify-center')}>
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-none bg-[#c76a1a] text-[#083728] shadow-sm">
                            <Compass className="h-5 w-5" />
                        </div>
                        <div className={cn('min-w-0 flex-1', collapsed && 'md:hidden')}>
                            <p className="font-editorial truncate text-lg font-semibold tracking-[-0.02em] text-[#fbf6e7]">
                                Compass Needle
                            </p>
                            <p className="font-mono-ui mt-1 truncate text-[10px] uppercase tracking-[0.22em] text-[#d8ceb8]/70">
                                MP Workspace
                            </p>
                        </div>
                        {setCollapsed && (
                            <Button
                                variant="ghost"
                                size="icon"
                                className={cn(
                                    'hidden h-8 w-8 rounded-none border border-white/10 bg-white/5 text-[#e6ddc9] hover:bg-white/10 hover:text-white md:flex',
                                    collapsed && 'md:hidden'
                                )}
                                onClick={() => setCollapsed(!collapsed)}
                                aria-label="Collapse sidebar"
                            >
                                <ChevronLeft className="h-4 w-4" />
                            </Button>
                        )}
                    </div>
                </div>

                <div className={cn('border-b border-white/10 px-4 py-4', collapsed && 'md:px-3')}>
                    <div className={cn('rounded-none border border-white/10 bg-white/5 p-3', collapsed && 'md:flex md:justify-center md:bg-transparent md:p-0 md:border-0')}>
                        <div className={cn('flex items-center gap-3', collapsed && 'md:justify-center')}>
                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-none bg-[#f2ebd9] text-sm font-semibold text-[#083728]">
                                {user?.display_name?.charAt(0)?.toUpperCase() || 'U'}
                            </div>
                            <div className={cn('min-w-0 flex-1', collapsed && 'md:hidden')}>
                                <p className="truncate text-sm font-semibold text-[#fbf6e7]">
                                    {user?.display_name}
                                </p>
                                <p className="truncate text-xs text-[#d8ceb8]/70">
                                    {user?.constituency || house}
                                </p>
                            </div>
                        </div>
                    </div>
                </div>

                <ScrollArea className="flex-1">
                    <div className="px-3 py-5">
                        <p className={cn(
                            'font-mono-ui px-3 text-[10px] uppercase tracking-[0.22em] text-[#d8ceb8]/60',
                            collapsed && 'md:text-center md:px-0'
                        )}>
                            Modules
                        </p>

                        <nav className="mt-3 space-y-1.5">
                            {NAV_ITEMS.filter(item => !item.mpOnly || user?.role === 'mp' || user?.role === 'admin').map((item) => {
                                const Icon = item.icon;
                                const active = pathname === item.path ||
                                    (item.path !== '/dashboard' && pathname.startsWith(item.path));
                                const badgeCount = item.badgeKey ? (badges[item.badgeKey] || 0) : 0;

                                const linkContent = (
                                    <Link
                                        href={item.path}
                                        className={cn(
                                            'group relative flex items-center gap-3 rounded-none border px-3 py-3 text-sm transition-all duration-200',
                                            active
                                                ? 'border-[#d8c39a]/40 bg-[#f2ebd9] text-[#083728] shadow-sm'
                                                : 'border-transparent text-[#eadfc6]/84 hover:border-white/10 hover:bg-white/5 hover:text-[#fbf6e7]',
                                            collapsed && 'md:justify-center md:px-2'
                                        )}
                                        onClick={() => setIsOpen?.(false)}
                                    >
                                        {active && <span className="absolute left-0 top-0 h-full w-1 bg-[#c76a1a]" />}
                                        <Icon className={cn('h-[18px] w-[18px] shrink-0', active ? 'text-[#0d6a4d]' : 'text-[#d8ceb8]/72 group-hover:text-[#fbf6e7]')} />
                                        <span className={cn('flex-1 truncate font-medium', collapsed && 'md:hidden')}>
                                            {item.name}
                                        </span>
                                        {badgeCount > 0 && (
                                            <div className={cn(collapsed && 'md:hidden')}>
                                                <NavBadge count={badgeCount} highlighted={active} />
                                            </div>
                                        )}
                                    </Link>
                                );

                                if (collapsed) {
                                    return (
                                        <Tooltip key={item.path} delayDuration={0}>
                                            <TooltipTrigger asChild className="hidden md:flex">
                                                {linkContent}
                                            </TooltipTrigger>
                                            <TooltipContent side="right" className="rounded-none border border-[#d7c7a6] bg-[#fbf6e7] text-[#1a1812]">
                                                <div className="flex items-center gap-2">
                                                    <span>{item.name}</span>
                                                    {badgeCount > 0 && <NavBadge count={badgeCount} highlighted={active} />}
                                                </div>
                                            </TooltipContent>
                                        </Tooltip>
                                    );
                                }

                                return <div key={item.path}>{linkContent}</div>;
                            })}
                        </nav>
                    </div>
                </ScrollArea>

                <div className={cn('border-t border-white/10 px-4 py-4', collapsed && 'md:px-3')}>
                    <div className={cn('mb-3 rounded-none border border-white/10 bg-white/5 p-3', collapsed && 'md:hidden')}>
                        <p className="font-mono-ui text-[10px] uppercase tracking-[0.22em] text-[#d8ceb8]/60">
                            System
                        </p>
                        <div className="mt-2 flex items-center gap-2 text-sm text-[#fbf6e7]">
                            <span className="h-2 w-2 rounded-full bg-[#c76a1a]" />
                            All systems operational
                        </div>
                        <p className="mt-1 text-xs text-[#d8ceb8]/70">
                            Case intake, drafter, and media workflows are live.
                        </p>
                    </div>

                    {collapsed && setCollapsed && (
                        <Button
                            variant="ghost"
                            size="icon"
                            className="mb-2 hidden h-10 w-full rounded-none border border-white/10 bg-white/5 text-[#e6ddc9] hover:bg-white/10 hover:text-white md:flex"
                            onClick={() => setCollapsed(false)}
                            aria-label="Expand sidebar"
                        >
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    )}

                    <Tooltip delayDuration={0}>
                        <TooltipTrigger asChild>
                            <Button
                                variant="ghost"
                                className={cn(
                                    'w-full justify-start rounded-none border border-white/10 bg-white/5 px-3 text-[#eadfc6] hover:bg-[#f2ebd9] hover:text-[#083728]',
                                    collapsed && 'md:justify-center md:px-2'
                                )}
                                onClick={onLogout}
                            >
                                <LogOut className="h-4 w-4 shrink-0" />
                                <span className={cn('ml-2', collapsed && 'md:hidden')}>Log out</span>
                            </Button>
                        </TooltipTrigger>
                        {collapsed && (
                            <TooltipContent side="right" className="rounded-none border border-[#d7c7a6] bg-[#fbf6e7] text-[#1a1812]">
                                Log out
                            </TooltipContent>
                        )}
                    </Tooltip>
                </div>
            </aside>
        </>
    );
}
