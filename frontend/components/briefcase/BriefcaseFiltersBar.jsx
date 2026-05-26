'use client';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import DashboardControlBar from '@/components/DashboardControlBar';
import { TABS } from '@/components/briefcase/briefcase-shared';
import { cn } from '@/lib/utils';

export default function BriefcaseFiltersBar(props) {
    const {
        assignedFilter,
        assemblyFilter,
        categoryFilter,
        color,
        criticalOnly,
        dateFrom,
        dateTo,
        filterOptions,
        onAssemblyChange,
        onAssignedChange,
        onCategoryChange,
        onClear,
        onCriticalOnlyChange,
        onDateFromChange,
        onDateToChange,
        onExport,
        onLocationChange,
        onPageSizeChange,
        onRefresh,
        onSearchInputChange,
        onSortOrderChange,
        onTabChange,
        optionLabel,
        pageSize,
        searchInput,
        sortOrder,
        staff,
        statusFilter,
        locationFilter,
    } = props;

    return (
        <>
            <div className="overflow-x-auto -mx-6 px-6">
                <Tabs value={statusFilter} onValueChange={onTabChange}>
                    <TabsList className="h-auto p-0 bg-transparent gap-6">
                        {TABS.map((tab) => (
                            <TabsTrigger
                                key={tab.key}
                                value={tab.key}
                                className={cn(
                                    'px-0 pb-3 rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none',
                                    'text-sm font-medium text-muted-foreground data-[state=active]:text-foreground'
                                )}
                                style={statusFilter === tab.key ? { borderColor: color, color } : {}}
                            >
                                {tab.label}
                            </TabsTrigger>
                        ))}
                    </TabsList>
                </Tabs>
            </div>

            {statusFilter !== 'clusters' && statusFilter !== 'deleted' && (
                <DashboardControlBar
                    className="mt-3"
                    search={searchInput}
                    onSearchChange={onSearchInputChange}
                    searchPlaceholder="Search by phone, message, ref, location..."
                    onRefresh={onRefresh}
                    onExport={onExport}
                    exportLabel="Export CSV"
                >
                    <select className="h-9 max-w-[180px] rounded border bg-background px-2 text-sm" value={categoryFilter} onChange={(e) => onCategoryChange(e.target.value)} aria-label="Filter by category">
                        <option value="">All categories</option>
                        {filterOptions.categories.map((option) => (
                            <option key={option.value} value={option.value}>{optionLabel(option)}</option>
                        ))}
                    </select>
                    <select className="h-9 max-w-[180px] rounded border bg-background px-2 text-sm" value={locationFilter} onChange={(e) => onLocationChange(e.target.value)} aria-label="Filter by location">
                        <option value="">All locations</option>
                        {filterOptions.locations.map((option) => (
                            <option key={option.value} value={option.value}>{optionLabel(option)}</option>
                        ))}
                    </select>
                    <select className="h-9 max-w-[190px] rounded border bg-background px-2 text-sm" value={assemblyFilter} onChange={(e) => onAssemblyChange(e.target.value)} aria-label="Filter by constituency">
                        <option value="">All constituencies</option>
                        {filterOptions.assemblies.map((option) => (
                            <option key={option.value} value={option.value}>{optionLabel(option)}</option>
                        ))}
                    </select>
                    <select className="h-9 rounded border bg-background px-2 text-sm" value={assignedFilter} onChange={(e) => onAssignedChange(e.target.value)}>
                        <option value="">All assignees</option>
                        {staff.map((member) => (
                            <option key={member.username} value={member.username}>{member.display_name || member.username}</option>
                        ))}
                    </select>
                    <Input type="date" className="h-9 w-[150px] text-sm" value={dateFrom} onChange={(e) => onDateFromChange(e.target.value)} aria-label="From date" />
                    <Input type="date" className="h-9 w-[150px] text-sm" value={dateTo} onChange={(e) => onDateToChange(e.target.value)} aria-label="To date" />
                    <select className="h-9 rounded border bg-background px-2 text-sm" value={sortOrder} onChange={(e) => onSortOrderChange(e.target.value)}>
                        <option value="newest">Newest first</option>
                        <option value="oldest">Oldest first</option>
                        <option value="updated">Recently updated</option>
                        <option value="critical">Critical first</option>
                    </select>
                    <label className="flex h-9 items-center gap-2 rounded border bg-background px-2 text-sm">
                        <input type="checkbox" checked={criticalOnly} onChange={(e) => onCriticalOnlyChange(e.target.checked)} />
                        Critical only
                    </label>
                    <select className="h-9 rounded border bg-background px-2 text-sm" value={pageSize} onChange={(e) => onPageSizeChange(Number(e.target.value))}>
                        {[25, 50, 100].map((count) => (
                            <option key={count} value={count}>{count} / page</option>
                        ))}
                    </select>
                    <Button variant="ghost" size="sm" onClick={onClear}>Clear</Button>
                </DashboardControlBar>
            )}
        </>
    );
}
