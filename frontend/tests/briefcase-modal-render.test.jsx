import React from 'react';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const { apiGetMock, apiPostMock } = vi.hoisted(() => ({ apiGetMock: vi.fn(), apiPostMock: vi.fn() }));
vi.mock('@/lib/api', () => ({ apiGet: apiGetMock, apiPost: apiPostMock, apiPatch: vi.fn(), apiDelete: vi.fn(), API_BASE: 'http://api.test', getAuthToken: () => 'token' }));
vi.mock('@/components/ui/toast', () => ({ useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() }) }));
import BriefcaseCaseModal from '@/components/briefcase/BriefcaseCaseModal';

const DELHI = (en) => ({ state: 'Delhi', supported: false, manual_reference_enabled: en, staff_assisted_tasks: en ? [] : null, reference_rule: en ? 'r' : null });
const KA = { state: 'Karnataka', supported: true, portal: { id: 3, portal_name: 'Karnataka Janaspandana (iPGRS)', base_url: 'https://ipgrs.karnataka.gov.in' } };
const MH = { state: 'Maharashtra', supported: true, portal: { id: 4, portal_name: 'Maharashtra Aaple Sarkar', base_url: 'https://x.test' } };
const CP = { state: 'Goa', supported: true, portal: { id: 2, portal_name: 'CPGRAMS', base_url: 'https://pgportal.gov.in' } };

function setup({ portal, detailExtra = {}, filed = true, govtExtra = null }) {
    const govt = filed ? { govt_status: 'submitted', govt_reference_number: '20260000001', govt_portal_id: 9 } : { govt_status: 'not_forwarded', govt_reference_number: null, govt_portal_id: null };
    apiGetMock.mockImplementation(async (path) => {
        if (path === '/api/govt-portal') return portal;
        if (/^\/api\/cases\/\d+$/.test(path)) return { id: 7, ...govt, status: 'in_progress', category: 'Health', raw_message: 'x', thread_cases: [], ...detailExtra };
        if (/\/govt$/.test(path)) return { case: { id: 7, ...govt, portal_name: 'ignored', ...(govtExtra || {}) } };
        if (path.endsWith('/govt/history')) return null;
        if (path === '/api/govt/sessions') return { sessions: [], global_count: 0, max_concurrent: 3 };
        if (path.includes('/activity')) return [];
        return {};
    });
}
const item = (extra = {}) => ({ id: 7, status: 'in_progress', category: 'Health', raw_message: 'x', created_at: '2026-10-30T03:00:00Z', govt_status: 'submitted', govt_reference_number: '20260000001', govt_portal_id: 9, case_metadata: {}, ...extra });
async function open(caseItem) {
    render(<BriefcaseCaseModal caseItem={caseItem} color="#000" onClose={() => {}} onStatusChange={() => {}} statusFilter="all_cases" staff={[]} user={{ username: 'mp', role: 'mp', is_primary: true }} onDeleteCase={() => {}} />);
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
    const row = screen.queryAllByText('GOVERNMENT SUBMISSION')[0];
    if (row) { await act(async () => { fireEvent.click(row); await new Promise((r) => setTimeout(r, 80)); }); }
}
const txt = () => document.body.textContent;
const portalCalls = () => apiGetMock.mock.calls.filter(([p]) => p === '/api/govt-portal').length;

beforeEach(() => { apiGetMock.mockReset(); apiPostMock.mockReset(); });

// Mounts the REAL BriefcaseCaseModal (only the network layer, toast and mobile hook are mocked). Guards against
// render-time crashes (e.g. a temporal-dead-zone ReferenceError) that detector unit tests and source pins cannot see.
describe('BriefcaseCaseModal real render - Delhi vs other portals', () => {
    it('Delhi filed case from a list row shows the Delhi callout and no generic status refresh', async () => {
        setup({ portal: DELHI(true) }); await open(item({ govt_portal_name: 'Delhi CM Jan Sunwai' }));
        expect(txt()).toMatch(/MANUAL FILING/); expect(txt()).toMatch(/Not verified by Needle/);
        expect(txt()).not.toMatch(/Check government status/); expect(portalCalls()).toBe(1);
    });
    it.each([
        ['Delhi row with no portal identity anywhere (row and detail) keeps the ORIGINAL presentation', DELHI(true), undefined],
        ['Karnataka', KA, 'Karnataka Janaspandana (iPGRS)'],
        ['Maharashtra', MH, 'Maharashtra Aaple Sarkar'],
        ['CPGRAMS', CP, 'CPGRAMS'],
        ['null portal name', KA, null],
    ])('%s: original presentation and status-refresh control', async (_n, portal, name) => {
        setup({ portal }); await open(item({ govt_portal_name: name }));
        expect(txt()).not.toMatch(/MANUAL FILING/); expect(txt()).not.toMatch(/Not verified by Needle/);
        expect(txt()).toMatch(/Check government status/); expect(portalCalls()).toBe(1);
    });
    it('Delhi flag OFF exposes no filing controls', async () => {
        setup({ portal: DELHI(false), filed: false }); await open(item({ govt_status: 'not_forwarded', govt_reference_number: null, govt_portal_id: null, govt_portal_name: null }));
        expect(txt()).not.toMatch(/Record the complaint number|Save complaint number/i);
        expect(document.querySelector('[data-testid="delhi-step-file"]')).toBeNull();
    });
    it('Delhi flag ON exposes the filing controls', async () => {
        setup({ portal: DELHI(true), filed: false }); await open(item({ govt_status: 'not_forwarded', govt_reference_number: null, govt_portal_id: null, govt_portal_name: null }));
        expect(document.querySelector('[data-testid="delhi-manual-reference"]')).not.toBeNull();
        expect(txt()).toMatch(/Record the complaint number|Save complaint number/i);
    });
});

describe('BriefcaseCaseModal real render - Delhi identity resolution', () => {
    it('cluster-opened Delhi case (row has no portal fields) is recognised from the case detail it already fetches', async () => {
        setup({ portal: DELHI(true), detailExtra: { govt_portal_id: 9, govt_portal_name: 'Delhi CM Jan Sunwai', govt_portal_state: 'Delhi' } });
        await open(item({ govt_portal_name: undefined, govt_portal_state: undefined, govt_portal_id: undefined }));
        expect(txt()).toMatch(/MANUAL FILING/); expect(txt()).not.toMatch(/Check government status/); expect(portalCalls()).toBe(1);
    });
    it('stable portal state wins over the display name, in both directions', async () => {
        setup({ portal: DELHI(true) }); await open(item({ govt_portal_name: 'Delhi Jan Sunwai (renamed)', govt_portal_state: 'Delhi' }));
        expect(txt()).toMatch(/MANUAL FILING/);
    });
    it('a non-Delhi state is never treated as Delhi even if the name matches', async () => {
        setup({ portal: KA }); await open(item({ govt_portal_name: 'Delhi CM Jan Sunwai', govt_portal_state: 'Karnataka' }));
        expect(txt()).not.toMatch(/MANUAL FILING/); expect(txt()).toMatch(/Check government status/);
    });
    it('filing a Delhi case in the same session switches the modal to the Delhi presentation without reopening', async () => {
        setup({ portal: DELHI(true), filed: false });
        const base = apiGetMock.getMockImplementation();
        let filedNow = false;
        apiGetMock.mockImplementation(async (path) => {
            if (filedNow && /\/govt$/.test(path)) return { case: { id: 7, govt_status: 'submitted', govt_reference_number: '20260000001', govt_portal_id: 9, portal_name: 'Delhi CM Jan Sunwai', portal_state: 'Delhi' } };
            return base(path);
        });
        apiPostMock.mockImplementation(async () => { filedNow = true; return { success: true, govt_reference_number: '20260000001', status: 'in_progress' }; });
        await open(item({ govt_status: 'not_forwarded', govt_reference_number: null, govt_portal_id: null, govt_portal_name: null }));
        expect(txt()).not.toMatch(/MANUAL FILING/);
        const input = screen.getByLabelText('Delhi portal reference number');
        await act(async () => { fireEvent.change(input, { target: { value: '20260000001' } }); });
        await act(async () => { fireEvent.click(screen.getByText('Save reference')); await new Promise((r) => setTimeout(r, 150)); });
        expect(apiPostMock).toHaveBeenCalled();
        expect(txt()).toMatch(/MANUAL FILING/); expect(txt()).toMatch(/Not verified by Needle/); expect(txt()).not.toMatch(/Check government status/);
        expect(portalCalls()).toBe(1);
    });
    it('same-session filing on Karnataka keeps the original presentation', async () => {
        setup({ portal: KA, filed: false });
        const base = apiGetMock.getMockImplementation();
        apiGetMock.mockImplementation(async (path) => (/\/govt$/.test(path) ? { case: { id: 7, govt_status: 'submitted', govt_reference_number: '1', govt_portal_id: 3, portal_name: 'Karnataka Janaspandana (iPGRS)', portal_state: 'Karnataka' } } : base(path)));
        await open(item({ govt_status: 'submitted', govt_reference_number: '1', govt_portal_name: 'Karnataka Janaspandana (iPGRS)' }));
        expect(txt()).not.toMatch(/MANUAL FILING/); expect(txt()).toMatch(/Check government status/); expect(portalCalls()).toBe(1);
    });
});
