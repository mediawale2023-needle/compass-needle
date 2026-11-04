import React from 'react';
import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { apiGetMock, searchParamsState } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
    searchParamsState: { value: new URLSearchParams() },
}));
vi.mock('@/lib/api', () => ({
    apiGet: apiGetMock, apiPost: vi.fn(), apiPatch: vi.fn(), apiDelete: vi.fn(), apiBlob: vi.fn(),
    API_BASE: 'http://api.test', getAuthToken: () => 'token',
}));
const { stableToast } = vi.hoisted(() => ({ stableToast: { success: () => {}, error: () => {}, info: () => {}, warning: () => {} } }));
vi.mock('@/components/ui/toast', () => ({ useToast: () => stableToast }));
vi.mock('next/navigation', () => ({
    useSearchParams: () => searchParamsState.value,
    useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
    usePathname: () => '/dashboard/sansadx',
}));

import BriefcaseCaseModal from '@/components/briefcase/BriefcaseCaseModal';
import useBriefcaseCases from '@/hooks/useBriefcaseCases';

const listCalls = () => apiGetMock.mock.calls.map(([path]) => path).filter((path) => path.startsWith('/api/cases?'));
const scopeOf = (path) => new URL(path, 'http://x').searchParams.get('data_scope');

beforeEach(() => {
    apiGetMock.mockReset();
    apiGetMock.mockImplementation(async (path) => {
        if (path.startsWith('/api/cases?')) return { cases: [], pages: 1, total: 0 };
        if (path.startsWith('/api/cases/filter-options')) return { statuses: [], categories: [], locations: [], assemblies: [] };
        return {};
    });
    searchParamsState.value = new URLSearchParams();
});

describe('Briefcase list requests carry the Live / Test / All scope', () => {
    it('defaults to live and sends data_scope on the list and the filter options', async () => {
        renderHook(() => useBriefcaseCases({ username: 'mp' }));
        await waitFor(() => expect(listCalls().length).toBeGreaterThan(0));
        expect(listCalls().every((path) => scopeOf(path) === 'live')).toBe(true);
        expect(apiGetMock.mock.calls.some(([path]) => path === '/api/cases/filter-options?data_scope=live')).toBe(true);
    });

    it('switching to test re-queries with data_scope=test and keeps the search term', async () => {
        const { result } = renderHook(() => useBriefcaseCases({ username: 'mp' }));
        await waitFor(() => expect(listCalls().length).toBeGreaterThan(0));
        apiGetMock.mockClear();
        await act(async () => { result.current.setDataScope('test'); });
        await waitFor(() => expect(listCalls().some((path) => scopeOf(path) === 'test')).toBe(true));
        expect(result.current.dataScope).toBe('test');
        expect(apiGetMock.mock.calls.some(([path]) => path === '/api/cases/filter-options?data_scope=test')).toBe(true);
    });

    it('restores the scope from the URL so a Test view survives a reload', async () => {
        searchParamsState.value = new URLSearchParams('data_scope=all');
        const { result } = renderHook(() => useBriefcaseCases({ username: 'mp' }));
        expect(result.current.dataScope).toBe('all');
        await waitFor(() => expect(listCalls().some((path) => scopeOf(path) === 'all')).toBe(true));
    });
});

describe('Briefcase case detail shows the synthetic designation', () => {
    const item = (extra = {}) => ({ id: 7, status: 'new', category: 'Infrastructure & Utilities', raw_message: 'x', created_at: '2026-11-04T09:01:00Z', govt_status: 'not_forwarded', case_metadata: {}, ...extra });
    async function open(caseItem, detailExtra = {}) {
        apiGetMock.mockImplementation(async (path) => {
            if (/^\/api\/cases\/\d+$/.test(path)) return { id: 7, status: 'new', category: 'Infrastructure & Utilities', raw_message: 'x', thread_cases: [], ...detailExtra };
            if (path === '/api/govt-portal') return { state: 'Delhi', supported: false, manual_reference_enabled: false };
            if (path.includes('/activity')) return [];
            return {};
        });
        render(<BriefcaseCaseModal caseItem={caseItem} color="#000" onClose={() => {}} onStatusChange={() => {}} statusFilter="all_cases" staff={[]} user={{ username: 'mp', role: 'mp', is_primary: true }} onDeleteCase={() => {}} />);
        await act(async () => { await new Promise((resolve) => setTimeout(resolve, 60)); });
    }

    it('shows TEST CASE and the disabled-actions notice for a synthetic case', async () => {
        await open(item({ is_synthetic_test_data: true }), { is_synthetic_test_data: true });
        const banner = screen.getAllByRole('status').find((node) => /TEST CASE/.test(node.textContent));
        expect(banner).toBeTruthy();
        expect(banner.textContent).toMatch(/TEST CASE/);
        expect(banner.textContent).toMatch(/government actions are disabled/i);
    });

    it('shows nothing for a live case, even if its wording looks synthetic', async () => {
        await open(item({ is_synthetic_test_data: false, raw_message: 'SYNTHETIC TEST DATA wording' }), { is_synthetic_test_data: false });
        expect(document.body.textContent).not.toMatch(/TEST CASE/);
    });
});
