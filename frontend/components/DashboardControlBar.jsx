'use client';

import { Search, RefreshCw, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

export default function DashboardControlBar({
    search,
    onSearchChange,
    searchPlaceholder = 'Search...',
    children,
    onRefresh,
    onExport,
    exportLabel = 'Export',
    exporting = false,
    className = '',
}) {
    return (
        <div className={cn('flex flex-col gap-3 rounded-lg border bg-muted/20 p-3 md:flex-row md:items-center md:justify-between', className)}>
            <div className="flex min-w-0 flex-1 flex-col gap-3 md:flex-row md:items-center">
                {onSearchChange && (
                    <div className="relative w-full md:max-w-sm">
                        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                            className="h-9 pl-8 text-sm"
                            placeholder={searchPlaceholder}
                            value={search}
                            onChange={e => onSearchChange(e.target.value)}
                        />
                    </div>
                )}
                {children && (
                    <div className="flex flex-wrap items-center gap-2">
                        {children}
                    </div>
                )}
            </div>
            {(onRefresh || onExport) && (
                <div className="flex shrink-0 items-center gap-2">
                    {onRefresh && (
                        <Button variant="outline" size="sm" onClick={onRefresh} className="gap-2">
                            <RefreshCw className="h-4 w-4" />
                            Refresh
                        </Button>
                    )}
                    {onExport && (
                        <Button variant="outline" size="sm" onClick={onExport} disabled={exporting} className="gap-2">
                            <Download className="h-4 w-4" />
                            {exporting ? 'Exporting...' : exportLabel}
                        </Button>
                    )}
                </div>
            )}
        </div>
    );
}
