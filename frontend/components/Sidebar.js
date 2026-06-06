'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { canAccessConvergence, canAccessSansadAI, getAccountLabel, getSeatBadge } from '@/lib/account';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
    LayoutDashboard,
    Mail,
    Briefcase,
    PenTool,
    Users,
    Bot,
    Archive,
    Settings,
    LogOut,
    ChevronLeft,
    ChevronRight,
    Newspaper,
} from 'lucide-react';

const NAV_ITEMS = [
    { name: 'Overview',    path: '/dashboard',            icon: LayoutDashboard },
    { name: 'Briefcase',   path: '/dashboard/sansadx',    icon: Briefcase,   badgeKey: 'briefcase' },
    { name: 'Letterbox',   path: '/dashboard/letterbox',  icon: Mail,        badgeKey: 'letterbox' },
    { name: 'Drafter',     path: '/dashboard/drafter',    icon: PenTool },
    { name: 'Sansad AI',   path: '/dashboard/sansadai',   icon: Bot,         access: canAccessSansadAI },
    { name: 'Convergence', path: '/dashboard/csr',        icon: Users,       access: canAccessConvergence },
    { name: 'Schemes',     path: '/dashboard/schemes',    icon: Newspaper },
    { name: 'Archives',    path: '/dashboard/archives',   icon: Archive },
    { name: 'Settings',    path: '/dashboard/settings',   icon: Settings },
];

export default function Sidebar({ user, onLogout, isOpen, setIsOpen, badges = {}, collapsed = false, setCollapsed }) {
    const pathname = usePathname();

    const initials = user?.display_name
        ? user.display_name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
        : 'MP';

    return (
        <>
            {/* Mobile backdrop */}
            <div
                className={cn(
                    'fixed inset-0 z-40 md:hidden transition-opacity duration-300',
                    'bg-[#003B2A]/70 backdrop-blur-sm',
                    isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none',
                )}
                onClick={() => setIsOpen?.(false)}
            />

            <aside
                className={cn(
                    'fixed left-0 top-0 z-50 h-screen flex flex-col',
                    'transform transition-all duration-300 ease-out',
                    'md:translate-x-0',
                    isOpen ? 'translate-x-0' : '-translate-x-full',
                    collapsed ? 'md:w-[60px]' : 'md:w-[220px]',
                    'w-[220px]',
                )}
                style={{ background: '#003B2A', color: '#E5DDC8' }}
            >
                {/* Logo */}
                <div
                    className={cn(
                        'flex items-center gap-3 px-[18px] py-4 shrink-0',
                        collapsed && 'md:justify-center md:px-2',
                    )}
                    style={{ borderBottom: '1px solid rgba(229,221,200,0.10)' }}
                >
                    <div className="h-8 w-8 flex items-center justify-center shrink-0 overflow-hidden rounded-[6px]">
                        <Image
                            src="/compass-needle-mark.svg"
                            alt="Compass Needle logo"
                            width={32}
                            height={32}
                            className="h-8 w-8 shrink-0"
                            priority
                        />
                    </div>
                    <div className={cn('flex-1 min-w-0', collapsed && 'md:hidden')}>
                        <p
                            className="font-semibold text-sm leading-none"
                            style={{ color: '#F5EFE0', fontFamily: '"Source Serif 4", serif' }}
                        >
                            Compass Needle
                        </p>
                        <p
                            className="text-[9px] tracking-[0.12em] uppercase mt-1"
                            style={{ color: 'rgba(229,221,200,0.55)', fontFamily: '"JetBrains Mono", monospace' }}
                        >
                            v3 · Operations
                        </p>
                    </div>
                    {setCollapsed && !collapsed && (
                        <button
                            className="hidden md:flex h-7 w-7 items-center justify-center opacity-40 hover:opacity-80 transition-opacity shrink-0"
                            onClick={() => setCollapsed(true)}
                            aria-label="Collapse sidebar"
                        >
                            <ChevronLeft className="h-4 w-4" style={{ color: '#E5DDC8' }} />
                        </button>
                    )}
                </div>

                {/* Nav */}
                <div className="flex-1 overflow-y-auto py-2 min-h-0">
                    <p
                        className={cn(
                            'text-[9px] tracking-[0.14em] uppercase px-[18px] pt-3 pb-1',
                            collapsed && 'md:hidden',
                        )}
                        style={{ color: 'rgba(229,221,200,0.45)', fontFamily: '"JetBrains Mono", monospace' }}
                    >
                        Modules
                    </p>

                    <nav>
                        {NAV_ITEMS.filter(item => !item.access || item.access(user)).map((item) => {
                            const Icon = item.icon;
                            const active =
                                pathname === item.path ||
                                (item.path !== '/dashboard' && !item.path.includes('?') && pathname.startsWith(item.path));
                            const badgeCount = item.badgeKey ? (badges[item.badgeKey] || 0) : 0;

                            const inner = (
                                <Link
                                    href={item.path}
                                    className={cn(
                                        'flex items-center gap-3 py-[7px] text-[12.5px] font-medium transition-all duration-150',
                                        collapsed ? 'md:justify-center md:px-0 md:py-2 px-[18px]' : 'px-[18px]',
                                    )}
                                    style={{
                                        color: active ? '#F5EFE0' : '#E5DDC8',
                                        background: active ? 'rgba(2,80,58,0.6)' : 'transparent',
                                        borderLeft: active ? '2px solid #C76A1A' : '2px solid transparent',
                                        marginLeft: '-1px',
                                        fontWeight: active ? 600 : 500,
                                        opacity: active ? 1 : 0.8,
                                    }}
                                    onClick={() => setIsOpen?.(false)}
                                >
                                    <Icon
                                        className="h-[14px] w-[14px] shrink-0"
                                        style={{ color: active ? '#F5EFE0' : 'rgba(229,221,200,0.65)' }}
                                        strokeWidth={active ? 2 : 1.5}
                                    />
                                    <span className={cn('flex-1 truncate', collapsed && 'md:hidden')}>{item.name}</span>
                                    {badgeCount > 0 && (
                                        <span
                                            className={cn('text-[10px] font-bold px-1.5 leading-5', collapsed && 'md:hidden')}
                                            style={{
                                                background: 'rgba(199,106,26,0.20)',
                                                color: '#C76A1A',
                                                fontFamily: '"JetBrains Mono", monospace',
                                            }}
                                        >
                                            {badgeCount > 99 ? '99+' : badgeCount}
                                        </span>
                                    )}
                                </Link>
                            );

                            if (collapsed) {
                                return (
                                    <Tooltip key={item.path} delayDuration={0}>
                                        <TooltipTrigger asChild>
                                            <div className="hidden md:block">{inner}</div>
                                        </TooltipTrigger>
                                        <TooltipContent side="right">
                                            {item.name}{badgeCount > 0 && ` · ${badgeCount}`}
                                        </TooltipContent>
                                    </Tooltip>
                                );
                            }
                            return <div key={item.path}>{inner}</div>;
                        })}
                    </nav>

                    {/* System section */}
                    <div
                        className={cn('mt-2 pt-2', collapsed && 'md:hidden')}
                        style={{ borderTop: '1px solid rgba(229,221,200,0.10)' }}
                    >
                        <p
                            className="text-[9px] tracking-[0.14em] uppercase px-[18px] pt-2 pb-1"
                            style={{ color: 'rgba(229,221,200,0.45)', fontFamily: '"JetBrains Mono", monospace' }}
                        >
                            System
                        </p>
                        <Link
                            href="/dashboard/settings"
                            className="flex items-center gap-3 py-[7px] px-[18px] text-[12.5px] transition-opacity"
                            style={{ color: '#E5DDC8', opacity: 0.65 }}
                        >
                            <Settings className="h-[14px] w-[14px] shrink-0" strokeWidth={1.5} />
                            <span>Settings</span>
                        </Link>
                    </div>
                </div>

                {/* Footer */}
                <div
                    className="shrink-0"
                    style={{ borderTop: '1px solid rgba(229,221,200,0.10)' }}
                >
                    {/* System status */}
                    <div className={cn('px-[18px] py-3', collapsed && 'md:hidden')}>
                        <div className="flex items-center gap-2 mb-1">
                            <span
                                className="h-2 w-2 rounded-full shrink-0"
                                style={{ background: '#006A4D', boxShadow: '0 0 0 3px rgba(0,106,77,0.25)' }}
                            />
                            <span className="text-[11px] font-semibold" style={{ color: '#F5EFE0' }}>
                                All systems operational
                            </span>
                        </div>
                        <p
                            className="text-[9.5px] tracking-[0.08em]"
                            style={{ color: 'rgba(229,221,200,0.5)', fontFamily: '"JetBrains Mono", monospace' }}
                        >
                            {user?.constituency} · {getSeatBadge(user)}
                        </p>
                    </div>

                    {/* User row */}
                    <div
                        className={cn(
                            'flex items-center gap-3 px-[18px] py-3',
                            collapsed && 'md:justify-center md:px-2',
                        )}
                        style={{ borderTop: '1px solid rgba(229,221,200,0.10)' }}
                    >
                        <div
                            className="h-8 w-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0"
                            style={{
                                background: 'rgba(0,106,77,0.5)',
                                color: '#F5EFE0',
                                fontFamily: '"Source Serif 4", serif',
                            }}
                        >
                            {initials}
                        </div>
                        <div className={cn('flex-1 min-w-0', collapsed && 'md:hidden')}>
                            <p className="text-[12px] font-semibold truncate" style={{ color: '#F5EFE0' }}>
                                {user?.display_name}
                            </p>
                            <p
                                className="text-[9.5px] tracking-[0.08em] truncate mt-0.5"
                                style={{ color: 'rgba(229,221,200,0.55)', fontFamily: '"JetBrains Mono", monospace' }}
                            >
                                {getAccountLabel(user)}
                            </p>
                        </div>

                        {collapsed && setCollapsed && (
                            <button
                                className="hidden md:flex h-7 w-7 items-center justify-center opacity-40 hover:opacity-80 transition-opacity"
                                onClick={() => setCollapsed(false)}
                                aria-label="Expand sidebar"
                            >
                                <ChevronRight className="h-4 w-4" style={{ color: '#E5DDC8' }} />
                            </button>
                        )}

                        {!collapsed && (
                            <button
                                className="hidden md:flex h-7 w-7 items-center justify-center opacity-40 hover:opacity-70 transition-opacity shrink-0"
                                onClick={onLogout}
                                aria-label="Log out"
                            >
                                <LogOut className="h-4 w-4" style={{ color: '#E5DDC8' }} />
                            </button>
                        )}
                    </div>

                    {/* Mobile logout */}
                    <div className="md:hidden px-4 pb-4">
                        <Button
                            variant="ghost"
                            size="sm"
                            className="w-full justify-start gap-2 text-[12px]"
                            style={{ color: 'rgba(229,221,200,0.7)' }}
                            onClick={onLogout}
                        >
                            <LogOut className="h-4 w-4" />
                            Log out
                        </Button>
                    </div>
                </div>
            </aside>
        </>
    );
}
