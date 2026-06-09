'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useToast } from '@/components/ui/toast';
import { apiBlob, apiDelete, apiGet, apiPatch } from '@/lib/api';
import { OTHER_CATEGORIES, OTHER_STATUSES } from '@/components/briefcase/briefcase-shared';

export function getBriefcaseRowHighlight(status, category) {
    const normalizedStatus = (status || '').toLowerCase();
    const normalizedCategory = (category || '').toLowerCase();
    if (normalizedStatus === 'new' || normalizedStatus === 'escalated' || normalizedCategory === 'emergency') {
        return 'border-l-4 border-l-[#C76A1A] bg-[#f9efe0]';
    }
    if (normalizedStatus === 'resolved') {
        return 'border-l-4 border-l-[#006A4D] bg-[#eef5f1]';
    }
    return '';
}

export default function useBriefcaseCases(user) {
    const toast = useToast();
    const searchParams = useSearchParams();
    const now = new Date();
    const todayIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const todayLabel = now.toLocaleDateString('en-IN', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
    });

    const [cases, setCases] = useState([]);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState(() => searchParams.get('status') || 'all_cases');
    const [categoryFilter, setCategoryFilter] = useState(() => searchParams.get('category') || '');
    const [locationFilter, setLocationFilter] = useState(() => searchParams.get('location') || '');
    const [assemblyFilter, setAssemblyFilter] = useState(() => searchParams.get('assembly') || '');
    const [filterOptions, setFilterOptions] = useState({ statuses: [], categories: [], locations: [], assemblies: [] });
    const [selected, setSelected] = useState(null);
    const [downloading, setDownloading] = useState(false);
    const [contactPhone, setContactPhone] = useState(null);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalCases, setTotalCases] = useState(0);
    const [selectedIds, setSelectedIds] = useState(new Set());
    const [staff, setStaff] = useState([]);
    const [searchInput, setSearchInput] = useState('');
    const [search, setSearch] = useState('');
    const [pageSize, setPageSize] = useState(25);
    const [assignedFilter, setAssignedFilter] = useState('');
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [criticalOnly, setCriticalOnly] = useState(false);
    const [sortOrder, setSortOrder] = useState('newest');
    const [refreshToken, setRefreshToken] = useState(0);
    const [hasNewCases, setHasNewCases] = useState(false);
    const [clusters, setClusters] = useState([]);
    const [loadingClusters, setLoadingClusters] = useState(false);
    const [deletedCases, setDeletedCases] = useState([]);
    const [loadingDeleted, setLoadingDeleted] = useState(false);

    function isResolvedLikeStatus(status) {
        return ['resolved', 'completed', 'closed'].includes(String(status || '').toLowerCase());
    }

    useEffect(() => {
        const status = searchParams.get('status') || 'all_cases';
        setStatusFilter(status === 'All' ? 'all_cases' : status);
        setCategoryFilter(searchParams.get('category') || '');
        setLocationFilter(searchParams.get('location') || '');
        setAssemblyFilter(searchParams.get('assembly') || '');
        setPage(1);
    }, [searchParams]);

    useEffect(() => {
        const timeout = setTimeout(() => {
            setSearch(searchInput);
            setPage(1);
        }, 350);
        return () => clearTimeout(timeout);
    }, [searchInput]);

    useEffect(() => {
        apiGet('/api/staff')
            .then((result) => setStaff(result.staff || []))
            .catch(() => { console.error('Failed to fetch staff'); });
    }, []);

    useEffect(() => {
        apiGet('/api/cases/filter-options')
            .then((result) => setFilterOptions({
                statuses: result.statuses || [],
                categories: result.categories || [],
                locations: result.locations || [],
                assemblies: result.assemblies || [],
            }))
            .catch(() => setFilterOptions({ statuses: [], categories: [], locations: [], assemblies: [] }));
    }, [refreshToken]);

    useEffect(() => {
        fetchClusters();
    }, [refreshToken]);

    function setUrlFilter(key, value) {
        const url = new URL(window.location.href);
        if (value) {
            url.searchParams.set(key, value);
        } else {
            url.searchParams.delete(key);
        }
        window.history.replaceState({}, '', url.toString());
    }

    function optionLabel(option) {
        return `${option.value}${option.count ? ` (${option.count})` : ''}`;
    }

    function applyCaseFilters(params) {
        if (statusFilter === 'others') {
            params.set('bucket', 'other');
        } else if (statusFilter === 'all_cases') {
            params.set('exclude_status', 'resolved,completed,closed');
            params.delete('exclude_categories');
        } else {
            params.set('status', statusFilter);
        }

        if (categoryFilter) params.set('category', categoryFilter);
        if (locationFilter) params.set('location', locationFilter);
        if (assemblyFilter) params.set('assembly', assemblyFilter);
        if (search) params.set('search', search);
        if (assignedFilter) params.set('assigned_to', assignedFilter);
        if (dateFrom) params.set('date_from', dateFrom);
        if (dateTo) params.set('date_to', dateTo);
        if (criticalOnly) params.set('critical', 'true');
        if (sortOrder) params.set('sort', sortOrder);
    }

    async function fetchClusters() {
        setLoadingClusters(true);
        try {
            const result = await apiGet('/api/clusters');
            setClusters(result.clusters || []);
        } catch {
            setClusters([]);
        } finally {
            setLoadingClusters(false);
        }
    }

    async function fetchDeleted() {
        setLoadingDeleted(true);
        try {
            const result = await apiGet('/api/cases/deleted');
            setDeletedCases(result.cases || []);
        } catch {
            setDeletedCases([]);
        } finally {
            setLoadingDeleted(false);
        }
    }

    useEffect(() => {
        if (statusFilter === 'deleted') {
            fetchDeleted();
            return;
        }

        let cancelled = false;

        async function fetchCases() {
            setLoading(true);
            try {
                const params = new URLSearchParams({
                    page: String(page),
                    limit: String(pageSize),
                });
                applyCaseFilters(params);
                const result = await apiGet(`/api/cases?${params}`);
                if (!cancelled) {
                    setCases(result.cases || []);
                    setTotalPages(result.pages || 1);
                    setTotalCases(result.total || 0);
                    setSelectedIds(new Set());
                    setHasNewCases(false);
                }
            } catch (error) {
                if (!cancelled) {
                    console.error(error);
                    toast.error('Failed to load cases');
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        fetchCases();
        return () => {
            cancelled = true;
        };
    }, [statusFilter, categoryFilter, locationFilter, assemblyFilter, page, user?.username, search, pageSize, assignedFilter, dateFrom, dateTo, criticalOnly, sortOrder, refreshToken, toast]);

    useEffect(() => {
        if (statusFilter === 'deleted') {
            return;
        }
        const interval = setInterval(async () => {
            if (document.visibilityState !== 'visible') {
                return;
            }
            try {
                const params = new URLSearchParams({ page: '1', limit: '1' });
                applyCaseFilters(params);
                const result = await apiGet(`/api/cases?${params}`);
                if ((result.total || 0) > totalCases) {
                    setHasNewCases(true);
                }
            } catch {
                // silent polling
            }
        }, 30000);
        return () => clearInterval(interval);
    }, [statusFilter, categoryFilter, locationFilter, assemblyFilter, totalCases, search, assignedFilter, dateFrom, dateTo, criticalOnly, sortOrder]);

    useEffect(() => {
        const caseId = searchParams.get('case_id');
        if (!caseId || cases.length === 0) {
            return;
        }
        const match = cases.find((item) => String(item.id) === caseId);
        if (match) {
            setSelected(match);
        }
    }, [cases, searchParams]);

    function switchTab(key) {
        setStatusFilter(key);
        setPage(1);
        setSearch('');
        setSearchInput('');
        const url = new URL(window.location.href);
        if (key === 'all_cases') {
            url.searchParams.delete('status');
        } else {
            url.searchParams.set('status', key);
        }
        window.history.replaceState({}, '', url.toString());
    }

    function refreshCases() {
        setHasNewCases(false);
        setPage(1);
        setRefreshToken((value) => value + 1);
    }

    function clearAdvancedFilters() {
        setAssignedFilter('');
        setDateFrom('');
        setDateTo('');
        setCriticalOnly(false);
        setSortOrder('newest');
        setCategoryFilter('');
        setLocationFilter('');
        setAssemblyFilter('');
        setSearchInput('');
        setSearch('');
        const url = new URL(window.location.href);
        ['category', 'location', 'assembly'].forEach((key) => url.searchParams.delete(key));
        window.history.replaceState({}, '', url.toString());
        setPage(1);
        setRefreshToken((value) => value + 1);
    }

    async function handleRestore(caseId) {
        try {
            await apiPatch(`/api/cases/${caseId}/restore`, {});
            setDeletedCases((current) => current.filter((item) => item.id !== caseId));
            toast.success('Case restored successfully');
        } catch (error) {
            toast.error(error.message || 'Failed to restore case');
        }
    }

    function clearCategoryFilter() {
        setCategoryFilter('');
        setPage(1);
        setUrlFilter('category', '');
    }

    function clearLocationFilter() {
        setLocationFilter('');
        setPage(1);
        setUrlFilter('location', '');
    }

    function clearAssemblyFilter() {
        setAssemblyFilter('');
        setPage(1);
        setUrlFilter('assembly', '');
    }

    function handleStatusChange(caseId, newStatus) {
        const resolvedLike = isResolvedLikeStatus(newStatus);
        const activeTab = !['resolved', 'deleted', 'clusters'].includes(String(statusFilter || '').toLowerCase());

        setCases((current) => current.flatMap((item) => {
            if (item.id === caseId) {
                return resolvedLike && activeTab ? [] : [{ ...item, status: newStatus }];
            }
            if (Array.isArray(item.thread_case_ids) && item.thread_case_ids.includes(caseId)) {
                if (resolvedLike && activeTab) {
                    const remainingIds = item.thread_case_ids.filter((id) => id !== caseId);
                    if (remainingIds.length === 0) {
                        return [];
                    }
                    return [{
                        ...item,
                        thread_case_ids: remainingIds,
                        thread_case_count: Math.max(remainingIds.length, 1),
                        pending_contact_count: Math.max(remainingIds.length - 1, 0),
                    }];
                }
                return [{ ...item }];
            }
            return [item];
        }));

        setSelected((current) => {
            if (!current) return current;
            if (current.id === caseId) {
                return resolvedLike && activeTab ? null : { ...current, status: newStatus };
            }
            if (Array.isArray(current.thread_case_ids) && current.thread_case_ids.includes(caseId)) {
                if (resolvedLike && activeTab) {
                    const remainingIds = current.thread_case_ids.filter((id) => id !== caseId);
                    if (remainingIds.length === 0) {
                        return null;
                    }
                    return {
                        ...current,
                        thread_case_ids: remainingIds,
                        thread_case_count: Math.max(remainingIds.length, 1),
                        pending_contact_count: Math.max(remainingIds.length - 1, 0),
                    };
                }
                return { ...current };
            }
            return current;
        });
        setRefreshToken((value) => value + 1);
    }

    async function deleteCase(caseId) {
        await apiDelete(`/api/cases/${caseId}`);
        setCases((current) => current.filter((item) => item.id !== caseId));
        setSelected((current) => current && current.id === caseId ? null : current);
        setSelectedIds((current) => {
            const next = new Set(current);
            next.delete(caseId);
            return next;
        });
        setRefreshToken((value) => value + 1);
    }

    async function bulkStatusChange(newStatus) {
        const ids = [...selectedIds];
        if (ids.length === 0) {
            return;
        }
        try {
            await Promise.all(ids.map((id) => apiPatch(`/api/cases/${id}/status`, { status: newStatus })));
            setCases((current) => current.map((item) => ids.includes(item.id) ? { ...item, status: newStatus } : item));
            setSelectedIds(new Set());
            toast.success(`Updated ${ids.length} case${ids.length !== 1 ? 's' : ''} to ${newStatus}`);
        } catch (error) {
            console.error(error);
            toast.error('Bulk update failed');
        }
    }

    async function bulkAssign(username) {
        const ids = [...selectedIds];
        if (ids.length === 0) {
            return;
        }
        try {
            await Promise.all(ids.map((id) => apiPatch(`/api/cases/${id}`, { assigned_to: username || null })));
            setCases((current) => current.map((item) => ids.includes(item.id) ? { ...item, assigned_to: username } : item));
            setSelectedIds(new Set());
            toast.success(`Assigned ${ids.length} case${ids.length !== 1 ? 's' : ''} to ${username || 'unassigned'}`);
        } catch (error) {
            console.error(error);
            toast.error('Bulk assign failed');
        }
    }

    async function bulkDelete() {
        const ids = [...selectedIds];
        if (ids.length === 0) {
            return;
        }
        if (!window.confirm(`Delete ${ids.length} selected case${ids.length !== 1 ? 's' : ''}? This cannot be undone.`)) {
            return;
        }
        try {
            await Promise.all(ids.map((id) => apiDelete(`/api/cases/${id}`)));
            setCases((current) => current.filter((item) => !ids.includes(item.id)));
            setSelected((current) => current && ids.includes(current.id) ? null : current);
            setSelectedIds(new Set());
            setTotalCases((current) => Math.max(0, current - ids.length));
            toast.success(`Deleted ${ids.length} case${ids.length !== 1 ? 's' : ''}`);
        } catch (error) {
            console.error(error);
            toast.error('Bulk delete failed');
        }
    }

    async function exportCasesCsv() {
        try {
            const params = new URLSearchParams();
            applyCaseFilters(params);
            const qs = params.toString() ? `?${params.toString()}` : '';
            const blob = await apiBlob(`/api/cases/export${qs}`);
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `briefcase_cases_${new Date().toISOString().slice(0, 10)}.csv`;
            link.click();
            URL.revokeObjectURL(url);
            toast.success('Cases exported');
        } catch (error) {
            toast.error(error.message || 'Failed to export cases');
        }
    }

    async function downloadReport() {
        setDownloading(true);
        try {
            const params = new URLSearchParams();
            if (statusFilter !== 'needs') params.set('status', statusFilter);
            if (categoryFilter) params.set('category', categoryFilter);
            if (locationFilter) params.set('location', locationFilter);
            if (assemblyFilter) params.set('assembly', assemblyFilter);
            const qs = params.toString() ? `?${params}` : '';
            const blob = await apiBlob(`/api/reports/grievance${qs}`);
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `grievance_report_${new Date().toISOString().slice(0, 10)}.pdf`;
            link.click();
            URL.revokeObjectURL(url);
            toast.success('Report downloaded successfully');
        } catch (error) {
            console.error('Report download failed:', error);
            toast.error('Failed to download report');
        } finally {
            setDownloading(false);
        }
    }

    const statusEntries = Array.isArray(filterOptions.statuses) ? filterOptions.statuses : [];
    const categoryEntries = Array.isArray(filterOptions.categories) ? filterOptions.categories : [];
    const countFrom = (entries, matcher) => {
        const found = entries.find((entry) => matcher(String(entry.value || '').toLowerCase()));
        return found?.count || 0;
    };
    const newCount = countFrom(statusEntries, (value) => value === 'new');
    const pendingReviewCount = countFrom(statusEntries, (value) => value === 'pending_review');
    const awaitingLocationCount = countFrom(statusEntries, (value) => value === 'awaiting_location');
    const inProgressCount = countFrom(statusEntries, (value) => value === 'in_progress');
    const resolvedCount = countFrom(statusEntries, (value) => value === 'resolved');
    const escalatedCount = countFrom(statusEntries, (value) => value === 'escalated');
    const activeCaseTotal = statusEntries.length > 0
        ? statusEntries
            .filter((entry) => !isResolvedLikeStatus(entry.value))
            .reduce((sum, entry) => sum + (entry.count || 0), 0)
        : Math.max(totalCases, cases.length);
    const uncategorisedCount =
        countFrom(categoryEntries, (value) => value === 'uncategorised' || value === 'general' || value === 'general grievance') ||
        cases.filter((item) => !item.category || /general|uncategor/i.test(String(item.category))).length;
    const slaRiskCount = cases.filter((item) => {
        if (item.is_critical || ['pending_review', 'escalated'].includes((item.status || '').toLowerCase())) {
            return true;
        }
        if (!item.created_at) {
            return false;
        }
        return (Date.now() - new Date(item.created_at).getTime()) / 3600000 >= 18;
    }).length;
    const othersCount =
        statusEntries
            .filter((entry) => OTHER_STATUSES.includes(String(entry.value || '').toLowerCase()))
            .reduce((sum, entry) => sum + (entry.count || 0), 0) +
        categoryEntries
            .filter((entry) => OTHER_CATEGORIES.map((value) => value.toLowerCase()).includes(String(entry.value || '').toLowerCase()))
            .reduce((sum, entry) => sum + (entry.count || 0), 0);

    const tabCounts = {
        new: newCount,
        in_progress: inProgressCount,
        resolved: resolvedCount,
        all_cases: activeCaseTotal,
        others: othersCount,
    };
    const triage = {
        needsYou: newCount + pendingReviewCount + awaitingLocationCount + escalatedCount ||
            cases.filter((item) => ['new', 'pending_review', 'awaiting_location', 'escalated'].includes((item.status || '').toLowerCase())).length,
        newToday: newCount || cases.filter((item) => String(item.created_at || '').startsWith(todayIso)).length,
        uncategorised: uncategorisedCount,
        slaRisk: slaRiskCount,
    };
    const subtitle = `${activeCaseTotal.toLocaleString()} active cases · ${triage.needsYou} need your attention · ${user?.constituency || 'Constituency'} · ${todayLabel}`;

    return {
        assemblyFilter,
        assignedFilter,
        bulkAssign,
        bulkDelete,
        bulkStatusChange,
        cases,
        categoryFilter,
        clearAdvancedFilters,
        clearAssemblyFilter,
        clearCategoryFilter,
        clearLocationFilter,
        clusters,
        color: user?.theme_color || '#006a4d',
        contactPhone,
        criticalOnly,
        dateFrom,
        dateTo,
        deletedCases,
        downloading,
        downloadReport,
        deleteCase,
        exportCasesCsv,
        filterOptions,
        handleRestore,
        handleStatusChange,
        hasNewCases,
        loading,
        loadingClusters,
        loadingDeleted,
        locationFilter,
        optionLabel,
        page,
        pageSize,
        refreshCases,
        search,
        searchInput,
        selected,
        selectedIds,
        setAssemblyFilter,
        setAssignedFilter,
        setCategoryFilter,
        setContactPhone,
        setCriticalOnly,
        setDateFrom,
        setDateTo,
        setHasNewCases,
        setLocationFilter,
        setPage,
        setPageSize,
        setSearchInput,
        setSelected,
        setSelectedIds,
        setSortOrder,
        setUrlFilter,
        sortOrder,
        staff,
        statusFilter,
        subtitle,
        switchTab,
        tabCounts,
        todayLabel,
        totalCases,
        totalPages,
        triage,
    };
}
