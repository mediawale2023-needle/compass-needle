import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import BriefcaseFiltersBar from '@/components/briefcase/BriefcaseFiltersBar';
import BriefcaseCasesTable from '@/components/briefcase/BriefcaseCasesTable';


const noop = () => {};

describe('Briefcase synthetic test-data controls', () => {
    it('offers Live, Test and All scopes and reports selection changes', () => {
        const onDataScopeChange = vi.fn();
        render(<BriefcaseFiltersBar
            statusFilter="all_cases" dataScope="live" onDataScopeChange={onDataScopeChange}
            onTabChange={noop} onRefresh={noop} onExport={noop} onCategoryChange={noop}
            onLocationChange={noop} onAssemblyChange={noop} onAssignedChange={noop}
            onDateFromChange={noop} onDateToChange={noop} onSortOrderChange={noop}
            onCriticalOnlyChange={noop} onPageSizeChange={noop} onClear={noop}
            filterOptions={{ statuses: [], categories: [], locations: [], assemblies: [] }}
            staff={[]} tabCounts={{}} pageSize={25} sortOrder="newest" criticalOnly={false}
        />);
        const select = screen.getByLabelText('Case data scope');
        expect(screen.getByRole('option', { name: 'Live cases' })).toBeTruthy();
        expect(screen.getByRole('option', { name: 'Test cases' })).toBeTruthy();
        expect(screen.getByRole('option', { name: 'All cases' })).toBeTruthy();
        fireEvent.change(select, { target: { value: 'test' } });
        expect(onDataScopeChange).toHaveBeenCalledWith('test');
    });

    it('renders an explicit badge only for provenance-marked synthetic rows', () => {
        window.matchMedia = vi.fn().mockReturnValue({ matches: true, addEventListener: noop, removeEventListener: noop });
        render(<BriefcaseCasesTable
            cases={[{
                id: 1, case_ref: 'SYN-T9-DL-001', raw_message: 'Synthetic complaint',
                status: 'new', category: 'Infrastructure & Utilities', created_at: '2026-11-04T09:01:00Z',
                is_synthetic_test_data: true,
            }]}
            loading={false} search="" statusFilter="all_cases" categoryFilter=""
            selectedIds={new Set()} setSelectedIds={noop} onSelectCase={noop}
        />);
        expect(screen.getByLabelText('Synthetic test case')).toHaveTextContent('TEST CASE');
    });
});
