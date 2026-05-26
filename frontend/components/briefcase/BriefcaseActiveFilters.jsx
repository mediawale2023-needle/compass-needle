'use client';

import { X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { TABS } from '@/components/briefcase/briefcase-shared';

export default function BriefcaseActiveFilters({
    assemblyFilter,
    casesCount,
    categoryFilter,
    color,
    loading,
    locationFilter,
    onClearAssembly,
    onClearCategory,
    onClearLocation,
    onResetStatus,
    statusFilter,
}) {
    if ((!categoryFilter && !locationFilter && !assemblyFilter && statusFilter === 'All') || statusFilter === 'clusters' || statusFilter === 'deleted') {
        return null;
    }

    return (
        <div className="px-6 py-3 border-b flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Active filters:</span>
            {statusFilter !== 'All' && (
                <Badge variant="secondary" className="gap-1">
                    Status: {TABS.find((tab) => tab.key === statusFilter)?.label || statusFilter}
                    <button onClick={onResetStatus} className="ml-1 hover:opacity-80">
                        <X className="h-3 w-3" />
                    </button>
                </Badge>
            )}
            {categoryFilter && (
                <Badge variant="default" className="gap-1" style={{ background: color }}>
                    Category: {categoryFilter}
                    <button onClick={onClearCategory} className="ml-1 hover:opacity-80">
                        <X className="h-3 w-3" />
                    </button>
                </Badge>
            )}
            {locationFilter && (
                <Badge variant="default" className="gap-1" style={{ background: color }}>
                    Location: {locationFilter}
                    <button onClick={onClearLocation} className="ml-1 hover:opacity-80">
                        <X className="h-3 w-3" />
                    </button>
                </Badge>
            )}
            {assemblyFilter && (
                <Badge variant="default" className="gap-1" style={{ background: color }}>
                    Constituency: {assemblyFilter}
                    <button onClick={onClearAssembly} className="ml-1 hover:opacity-80">
                        <X className="h-3 w-3" />
                    </button>
                </Badge>
            )}
            <span className="text-xs text-muted-foreground ml-1">
                {loading ? '...' : `${casesCount} case${casesCount !== 1 ? 's' : ''}`}
            </span>
        </div>
    );
}
