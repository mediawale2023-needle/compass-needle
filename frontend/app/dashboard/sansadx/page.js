'use client';

import { Suspense } from 'react';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import BriefcaseActiveFilters from '@/components/briefcase/BriefcaseActiveFilters';
import BriefcaseBulkActions from '@/components/briefcase/BriefcaseBulkActions';
import BriefcaseCaseModal from '@/components/briefcase/BriefcaseCaseModal';
import BriefcaseCasesTable from '@/components/briefcase/BriefcaseCasesTable';
import BriefcaseClustersBanner from '@/components/briefcase/BriefcaseClustersBanner';
import BriefcaseClustersView from '@/components/briefcase/BriefcaseClustersView';
import BriefcaseContactPanel from '@/components/briefcase/BriefcaseContactPanel';
import BriefcaseDeletedCasesView from '@/components/briefcase/BriefcaseDeletedCasesView';
import BriefcaseFiltersBar from '@/components/briefcase/BriefcaseFiltersBar';
import BriefcaseHeader from '@/components/briefcase/BriefcaseHeader';
import BriefcaseNewCasesNotice from '@/components/briefcase/BriefcaseNewCasesNotice';
import BriefcasePagination from '@/components/briefcase/BriefcasePagination';
import BriefcaseTriageStrip from '@/components/briefcase/BriefcaseTriageStrip';
import { briefcasePalette as P } from '@/components/briefcase/briefcase-shared';
import useBriefcaseCases from '@/hooks/useBriefcaseCases';

function BriefcaseInner() {
    const { user } = useAuth();
    const briefcase = useBriefcaseCases(user);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, paddingBottom: 24 }}>
            <BriefcaseHeader
                searchInput={briefcase.searchInput}
                onSearchInputChange={briefcase.setSearchInput}
                subtitle={briefcase.subtitle}
                user={user}
            />

            <BriefcaseTriageStrip triage={briefcase.triage} />

            <BriefcaseClustersBanner
                clusters={briefcase.clusters}
                onOpenClusters={() => briefcase.switchTab('clusters')}
            />

            {briefcase.hasNewCases && (
                <BriefcaseNewCasesNotice
                    onRefresh={() => {
                        briefcase.setHasNewCases(false);
                        briefcase.setPage(1);
                    }}
                />
            )}

            <section
                style={{
                    border: `1px solid ${P.hair}`,
                    background: P.paper,
                    boxShadow: '0 1px 0 rgba(19,52,43,0.03)',
                }}
            >
                <BriefcaseFiltersBar
                    statusFilter={briefcase.statusFilter}
                    color={briefcase.color}
                    onTabChange={briefcase.switchTab}
                    searchInput={briefcase.searchInput}
                    onSearchInputChange={briefcase.setSearchInput}
                    onRefresh={briefcase.refreshCases}
                    onExport={briefcase.exportCasesCsv}
                    categoryFilter={briefcase.categoryFilter}
                    onCategoryChange={(value) => {
                        briefcase.setCategoryFilter(value);
                        briefcase.setUrlFilter('category', value);
                        briefcase.setPage(1);
                    }}
                    locationFilter={briefcase.locationFilter}
                    onLocationChange={(value) => {
                        briefcase.setLocationFilter(value);
                        briefcase.setUrlFilter('location', value);
                        briefcase.setPage(1);
                    }}
                    assemblyFilter={briefcase.assemblyFilter}
                    onAssemblyChange={(value) => {
                        briefcase.setAssemblyFilter(value);
                        briefcase.setUrlFilter('assembly', value);
                        briefcase.setPage(1);
                    }}
                    assignedFilter={briefcase.assignedFilter}
                    onAssignedChange={(value) => {
                        briefcase.setAssignedFilter(value);
                        briefcase.setPage(1);
                    }}
                    dateFrom={briefcase.dateFrom}
                    onDateFromChange={(value) => {
                        briefcase.setDateFrom(value);
                        briefcase.setPage(1);
                    }}
                    dateTo={briefcase.dateTo}
                    onDateToChange={(value) => {
                        briefcase.setDateTo(value);
                        briefcase.setPage(1);
                    }}
                    sortOrder={briefcase.sortOrder}
                    onSortOrderChange={(value) => {
                        briefcase.setSortOrder(value);
                        briefcase.setPage(1);
                    }}
                    criticalOnly={briefcase.criticalOnly}
                    onCriticalOnlyChange={(value) => {
                        briefcase.setCriticalOnly(value);
                        briefcase.setPage(1);
                    }}
                    pageSize={briefcase.pageSize}
                    onPageSizeChange={(value) => {
                        briefcase.setPageSize(value);
                        briefcase.setPage(1);
                    }}
                    onClear={briefcase.clearAdvancedFilters}
                    filterOptions={briefcase.filterOptions}
                    optionLabel={briefcase.optionLabel}
                    staff={briefcase.staff}
                    tabCounts={briefcase.tabCounts}
                />

                <BriefcaseActiveFilters
                    assemblyFilter={briefcase.assemblyFilter}
                    casesCount={briefcase.cases.length}
                    categoryFilter={briefcase.categoryFilter}
                    color={briefcase.color}
                    loading={briefcase.loading}
                    locationFilter={briefcase.locationFilter}
                    onClearAssembly={briefcase.clearAssemblyFilter}
                    onClearCategory={briefcase.clearCategoryFilter}
                    onClearLocation={briefcase.clearLocationFilter}
                    onResetStatus={() => briefcase.switchTab('all_cases')}
                    statusFilter={briefcase.statusFilter}
                />

                <BriefcaseBulkActions
                    selectedCount={briefcase.selectedIds.size}
                    onStatusChange={briefcase.bulkStatusChange}
                    onAssign={briefcase.bulkAssign}
                    onClear={() => briefcase.setSelectedIds(new Set())}
                    staff={briefcase.staff}
                />

                {briefcase.statusFilter === 'clusters' ? (
                    <BriefcaseClustersView
                        clusters={briefcase.clusters}
                        loading={briefcase.loadingClusters}
                        onSelectCase={briefcase.setSelected}
                    />
                ) : briefcase.statusFilter === 'deleted' ? (
                    <BriefcaseDeletedCasesView
                        deletedCases={briefcase.deletedCases}
                        loading={briefcase.loadingDeleted}
                        onRestore={briefcase.handleRestore}
                    />
                ) : (
                    <BriefcaseCasesTable
                        cases={briefcase.cases}
                        loading={briefcase.loading}
                        search={briefcase.search}
                        statusFilter={briefcase.statusFilter}
                        categoryFilter={briefcase.categoryFilter}
                        selectedIds={briefcase.selectedIds}
                        setSelectedIds={briefcase.setSelectedIds}
                        onSelectCase={briefcase.setSelected}
                        onOpenContact={briefcase.setContactPhone}
                    />
                )}

                {briefcase.statusFilter !== 'clusters' && briefcase.statusFilter !== 'deleted' && (
                    <BriefcasePagination
                        page={briefcase.page}
                        totalPages={briefcase.totalPages}
                        totalCases={briefcase.totalCases}
                        shown={briefcase.cases.length}
                        onPrevious={() => briefcase.setPage((value) => Math.max(1, value - 1))}
                        onNext={() => briefcase.setPage((value) => value + 1)}
                    />
                )}
            </section>

            <BriefcaseCaseModal
                caseItem={briefcase.selected}
                color={briefcase.color}
                onClose={() => briefcase.setSelected(null)}
                onStatusChange={briefcase.handleStatusChange}
                staff={briefcase.staff}
                user={user}
            />

            <BriefcaseContactPanel
                phone={briefcase.contactPhone}
                color={briefcase.color}
                onClose={() => briefcase.setContactPhone(null)}
            />
        </div>
    );
}

export default function BriefcasePage() {
    return (
        <Suspense fallback={
            <div className="flex items-center justify-center py-20">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        }>
            <BriefcaseInner />
        </Suspense>
    );
}
