'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
    LayoutDashboard,
    Mail,
    Briefcase,
    BookOpen,
    PenTool,
    Gift,
    Users,
    Archive,
    Settings,
    LogOut,
    Compass,
    ChevronLeft,
    ChevronRight,
} from 'lucide-react';

const NAV_ITEMS = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Letterbox', path: '/dashboard/letterbox', icon: Mail, badgeKey: 'letterbox' },
    { name: 'Briefcase', path: '/dashboard/sansadx', icon: Briefcase, badgeKey: 'briefcase' },
    { name: 'Research Desk', path: '/dashboard/copilot', icon: BookOpen },
    { name: 'Drafter', path: '/dashboard/drafter', icon: PenTool },
    { name: 'Ministry Watch', path: '/dashboard/schemes', icon: Gift },
    { name: 'CSR Intelligence', path: '/dashboard/csr', icon: Users },
    { name: 'Archives', path: '/dashboard/archives', icon: Archive },
    { name: 'Settings', path: '/dashboard/settings', icon: Settings },
];

function NavBadge({ count }) {
    if (!count || count < 1) return null;
    return (
        <Badge variant="destructive" className="h-5 min-w-5 px-1.5 text-[10px] font-bold">
            {count > 99 ? '99+' : count}
        </Badge>
    );
}

export default function Sidebar({ user, onLogout, isOpen, setIsOpen, badges = {}, collapsed = false, setCollapsed }) {
    const pathname = usePathname();
    const house = user?.house || 'Lok Sabha';
    const isLokSabha = house.toLowerCase().includes('lok');

    return (
        <>
            {/* Mobile Backdrop */}
            <div
                className={cn(
                    "fixed inset-0 bg-foreground/20 backdrop-blur-sm z-40 md:hidden transition-opacity duration-300",
                    isOpen ? "opacity-100" : "opacity-0 pointer-events-none"
                )}
                onClick={() => setIsOpen?.(false)}
            />

            {/* Sidebar */}
            <aside
                className={cn(
                    "fixed left-0 top-0 z-50 h-screen flex flex-col bg-card border-r border-border",
                    "transform transition-all duration-300 ease-out",
                    "md:translate-x-0",
                    isOpen ? "translate-x-0" : "-translate-x-full",
                    collapsed ? "md:w-[72px]" : "md:w-64",
                    "w-72"
                )}
            >
                {/* Logo Section */}
                <div className={cn("flex items-center gap-3 px-4 h-16 border-b border-border", collapsed && "md:justify-center md:px-2")}>
                    <div className={cn(
                        "h-10 w-10 rounded-xl flex items-center justify-center shrink-0 shadow-sm",
                        isLokSabha ? "bg-primary" : "bg-[hsl(350,88%,35%)]"
                    )}>
                        <Compass className="h-5 w-5 text-primary-foreground" />
                    </div>
                    <div className={cn("flex-1 min-w-0", collapsed && "md:hidden")}>
                        <h1 className="font-bold text-foreground truncate">Compass Needle</h1>
                        <p className="text-xs text-muted-foreground truncate">{house}</p>
                    </div>
                    
                    {/* Collapse toggle - desktop only */}
                    {setCollapsed && (
                        <Button
                            variant="ghost"
                            size="icon"
                            className={cn("hidden md:flex h-8 w-8 shrink-0", collapsed && "md:hidden")}
                            onClick={() => setCollapsed(!collapsed)}
                        >
                            <ChevronLeft className="h-4 w-4" />
                        </Button>
                    )}
                </div>

                {/* User Info */}
                <div className={cn("px-4 py-3 border-b border-border", collapsed && "md:px-2 md:py-3")}>
                    <div className={cn("flex items-center gap-3", collapsed && "md:justify-center")}>
                        <div className={cn(
                            "h-9 w-9 rounded-full flex items-center justify-center text-sm font-semibold shrink-0",
                            "bg-secondary text-secondary-foreground"
                        )}>
                            {user?.display_name?.charAt(0)?.toUpperCase() || 'U'}
                        </div>
                        <div className={cn("flex-1 min-w-0", collapsed && "md:hidden")}>
                            <p className="text-sm font-medium text-foreground truncate">
                                {user?.display_name}
                            </p>
                            <p className="text-xs text-muted-foreground truncate">
                                {user?.constituency}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Navigation */}
                <ScrollArea className="flex-1 py-2">
                    <nav className="px-2 space-y-1">
                        {NAV_ITEMS.map((item) => {
                            const Icon = item.icon;
                            const active = pathname === item.path || 
                                (item.path !== '/dashboard' && pathname.startsWith(item.path));
                            const badgeCount = item.badgeKey ? (badges[item.badgeKey] || 0) : 0;

                            const linkContent = (
                                <Link
                                    href={item.path}
                                    className={cn(
                                        "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                                        "hover:bg-accent hover:text-accent-foreground",
                                        active 
                                            ? "bg-primary/10 text-primary" 
                                            : "text-muted-foreground",
                                        collapsed && "md:justify-center md:px-2"
                                    )}
                                    onClick={() => setIsOpen?.(false)}
                                >
                                    <Icon className={cn(
                                        "h-5 w-5 shrink-0 transition-colors",
                                        active ? "text-primary" : "text-muted-foreground"
                                    )} />
                                    <span className={cn("flex-1", collapsed && "md:hidden")}>
                                        {item.name}
                                    </span>
                                    {badgeCount > 0 && (
                                        <div className={cn(collapsed && "md:hidden")}>
                                            <NavBadge count={badgeCount} />
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
                                        <TooltipContent side="right" className="hidden md:block">
                                            <div className="flex items-center gap-2">
                                                {item.name}
                                                {badgeCount > 0 && <NavBadge count={badgeCount} />}
                                            </div>
                                        </TooltipContent>
                                    </Tooltip>
                                );
                            }

                            return <div key={item.path}>{linkContent}</div>;
                        })}
                    </nav>
                </ScrollArea>

                {/* Footer */}
                <div className={cn("p-3 border-t border-border", collapsed && "md:p-2")}>
                    {collapsed && setCollapsed && (
                        <Button
                            variant="ghost"
                            size="icon"
                            className="hidden md:flex w-full h-10 mb-2"
                            onClick={() => setCollapsed(false)}
                        >
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    )}
                    <Tooltip delayDuration={0}>
                        <TooltipTrigger asChild>
                            <Button
                                variant="ghost"
                                className={cn(
                                    "w-full justify-start text-muted-foreground hover:text-destructive hover:bg-destructive/10",
                                    collapsed && "md:justify-center md:px-2"
                                )}
                                onClick={onLogout}
                            >
                                <LogOut className="h-4 w-4 shrink-0" />
                                <span className={cn("ml-2", collapsed && "md:hidden")}>Log out</span>
                            </Button>
                        </TooltipTrigger>
                        {collapsed && (
                            <TooltipContent side="right" className="hidden md:block">
                                Log out
                            </TooltipContent>
                        )}
                    </Tooltip>
                </div>
            </aside>
        </>
    );
}
