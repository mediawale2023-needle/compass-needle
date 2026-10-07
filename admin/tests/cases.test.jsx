import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { vi } from 'vitest';

const { apiGetMock, apiPostMock, apiPatchMock, replaceMock, searchRef } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
    apiPostMock: vi.fn(),
    apiPatchMock: vi.fn(),
    replaceMock: vi.fn(),
    searchRef: { current: '' },
}));
vi.mock('@/lib/api', () => ({
    apiGet: (p) => apiGetMock(p),
    apiPost: (p, b) => apiPostMock(p, b),
    apiPatch: (p, b) => apiPatchMock(p, b),
}));
vi.mock('next/navigation', () => ({
    usePathname: () => '/dashboard/cases-intelligence/explorer',
    useRouter: () => ({ replace: replaceMock, push: vi.fn() }),
    useSearchParams: () => new URLSearchParams(searchRef.current),
}));
vi.mock('next/link', () => ({ default: ({ href, children, ...props }) => <a href={href} {...props}>{children}</a> }));

import CaseIntelligencePage from '@/components/admin-domains/cases-intelligence/CaseIntelligencePage';
import {
    activePreset,
    analysisFacts,
    caseAge,
    caseTabs,
    describeActivity,
    explorerQuery,
    filtersFromParams,
    hasGovernmentRecord,
    searchCases,
    timelineItems,
} from '@/lib/admin-data';

const ROWS = [
    { id: 1042, tenant_id: 2, mp: 'Avichal Dubey', constituency: 'Udaipur', phone: '+919400000218', category: 'Water Supply', status: 'in_progress', location: 'Kheda', assembly: 'Girwa', message: 'No tap water in Kheda', created: '2026-09-30 18:47', created_at: '2026-09-30T18:47:00', critical: true, priority: 'critical', assigned_to: 'kavya', case_ref: 'UDR-1042', is_deleted: false },
    { id: 1041, tenant_id: 3, mp: 'Priya Rao', constituency: 'Belagavi', phone: '+919800000101', category: 'Roads', status: 'new', location: '-', assembly: '-', message: 'Road near the school is broken', created: '2026-10-05 09:12', created_at: '2026-10-05T09:12:00', critical: false, priority: 'standard', assigned_to: null, case_ref: null, is_deleted: false },
];

const FULL_DETAIL = {
    id: 1042, tenant_id: 2, mp_name: 'Avichal Dubey', mp_constituency: 'Udaipur', phone: '+919400000218', category: 'Water Supply',
    status: 'in_progress', critical: true, location: 'Kheda', assembly: 'Girwa', raw_message: 'नल में पानी नहीं आ रहा', response_to_citizen: 'We are on it',
    notes_for_staff: 'Called the JE', case_ref: 'UDR-1042', priority: 'critical', assigned_to: 'kavya', is_deleted: false, problem_domain: 'Water Supply', problem_subdomain: null,
    timestamps: { created_at: '2026-09-30T18:47:00', status_changed_at: '2026-10-01T11:02:00', resolved_at: null },
    government: { status: 'submitted', department: 'PHED', reference_number: 'PHED/UDR/412', status_updated_at: '2026-10-04T16:20:00', last_forwarded_to_citizen_at: null, portal: { name: 'Rajasthan Sampark', state: 'Rajasthan', type: 'state_branded' } },
    analysis: { summary: 'Tap water outage in Kheda.', ai_category: 'Water Supply', ai_subcategory: 'Piped supply', ai_confidence: 0.82, category_decided_by: 'ai', needs_review: true, classification_mode: 'shadow', language: 'hindi', english_translation: 'No water in the tap', department_mentioned: null, scheme_mentioned: null, geography: { confidence: 'high', source: 'gazetteer', needs_review: false } },
    activity: [
        { username: 'system', action: 'status_change', old_value: 'new', new_value: 'in_progress', details: null, created_at: '2026-10-01T11:02:00' },
        { username: 'kavya', action: 'govt_submitted', old_value: null, new_value: 'PHED/UDR/412', details: null, created_at: '2026-10-04T16:20:00' },
    ],
    messages: { inbound: [{ id: 1, status: 'processed', message_type: 'text', created_at: '2026-09-30T18:47:00' }], outbound: [{ id: 9, status: 'sent', body: 'We have registered your complaint.', template_key: 'ack', last_error: null, created_at: '2026-09-30T18:47:10' }] },
};

const BARE_DETAIL = {
    id: 1041, tenant_id: 3, mp_name: 'Priya Rao', mp_constituency: 'Belagavi', phone: '+919800000101', category: 'Roads', status: 'new', critical: false,
    location: '-', assembly: '-', raw_message: 'Road near the school is broken', response_to_citizen: '', notes_for_staff: '', priority: 'standard', assigned_to: null,
    timestamps: { created_at: '2026-10-05T09:12:00' }, government: { status: 'not_forwarded', portal: null },
    analysis: { summary: null, geography: {} }, activity: [], messages: { inbound: [], outbound: [] },
};

function explorerPayload(rows = ROWS) {
    return { total: rows.length, cases: rows, filter_options: { categories: ['Roads', 'Water Supply'], statuses: ['in_progress', 'new'], mps: [{ id: 2, name: 'Avichal Dubey', constituency: 'Udaipur' }, { id: 3, name: 'Priya Rao', constituency: 'Belagavi' }], priorities: ['critical', 'high', 'standard', 'low'] } };
}

function routeApi(overrides = {}) {
    apiGetMock.mockImplementation(async (path) => {
        if (path in overrides) {
            const value = overrides[path];
            if (value instanceof Error) throw value;
            return value;
        }
        if (path.startsWith('/api/admin/cases/explorer')) return explorerPayload();
        if (path === '/api/admin/cases/1042') return FULL_DETAIL;
        if (path === '/api/admin/cases/1041') return BARE_DETAIL;
        throw new Error(`unexpected ${path}`);
    });
}

function setDesktop(desktop) {
    window.matchMedia = (query) => ({
        matches: desktop && /min-width:\s*1024px/.test(query),
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
    });
}

beforeEach(() => {
    apiGetMock.mockReset();
    apiPostMock.mockReset();
    apiPatchMock.mockReset();
    replaceMock.mockReset();
    searchRef.current = '';
    setDesktop(true);
});

describe('case explorer data helpers', () => {
    it('maps Account 360 tenant links onto the real mp_id filter', () => {
        const filters = filtersFromParams(new URLSearchParams('tenant_id=9'));
        expect(filters.mp_id).toBe('9');
        expect(explorerQuery(filters)).toBe('?mp_id=9');
        expect(explorerQuery({ priority: 'critical', assignment: 'unassigned', status: '' })).toBe('?priority=critical&assignment=unassigned');
    });

    it('presets map one-to-one onto real filters', () => {
        expect(activePreset({})).toBe('all');
        expect(activePreset({ priority: 'critical' })).toBe('critical');
        expect(activePreset({ assignment: 'unassigned' })).toBe('unassigned');
        expect(activePreset({ priority: 'high' })).toBeNull();
    });

    it('only flags ageing for open cases past the shared 14-day threshold', () => {
        const now = new Date('2026-10-07T10:00:00Z');
        expect(caseAge('2026-09-20T10:00:00', 'new', now)).toMatchObject({ days: 17, label: '17d', tone: 'warning' });
        expect(caseAge('2026-09-20T10:00:00', 'resolved', now).tone).toBe('neutral');
        expect(caseAge('2026-10-07T07:00:00', 'new', now).label).toBe('3h');
        expect(caseAge(null, 'new', now).label).toBe('—');
    });

    it('offers only tabs that have real data', () => {
        expect(caseTabs(FULL_DETAIL).map((t) => t.value)).toEqual(['overview', 'timeline', 'government', 'notes', 'messages']);
        expect(caseTabs(BARE_DETAIL).map((t) => t.value)).toEqual(['overview']);
        expect(caseTabs({ ...BARE_DETAIL, activity: null, messages: { inbound: null, outbound: [] } }).map((t) => t.value)).toEqual(['overview']);
        expect(hasGovernmentRecord({ status: 'not_forwarded' })).toBe(false);
        expect(hasGovernmentRecord({ status: 'submitted' })).toBe(true);
    });

    it('describes recorded activity without inventing events', () => {
        expect(describeActivity({ action: 'status_change', old_value: 'new', new_value: 'in_progress' })).toBe('Status changed from New to In progress');
        expect(describeActivity({ action: 'case_updated', details: "{'status': 'resolved', 'notes_for_staff': 'x'}" })).toBe('Case updated: status, notes for staff');
        expect(describeActivity({ action: 'some_new_action' })).toBe('Some new action');
        const items = timelineItems(FULL_DETAIL.activity);
        expect(items).toHaveLength(2);
        expect(items[0].title).toMatch(/Filed with government portal/);
        expect(items[1].actor).toBe('System');
    });

    it('lists only AI fields the pipeline actually wrote', () => {
        const labels = analysisFacts(FULL_DETAIL.analysis).map((f) => f.label);
        expect(labels).toEqual(['Suggested category', 'Category source', 'Classification mode', 'Detected language', 'Location match']);
        expect(analysisFacts({ geography: {} })).toEqual([]);
    });

    it('searches only the loaded rows', () => {
        expect(searchCases(ROWS, '#1041').map((r) => r.id)).toEqual([1041]);
        expect(searchCases(ROWS, 'kheda').map((r) => r.id)).toEqual([1042]);
        expect(searchCases(ROWS, '')).toHaveLength(2);
    });
});

describe('Case Explorer workspace', () => {
    it('keeps the explorer primary with analytics and case health as secondary views', async () => {
        routeApi({ '/api/admin/cases/health': { total_cases: 10, active_mps: 2, resolved: 4, critical: 1, status_breakdown: [], mp_cases: [], activity: [], volume_30d: [] } });
        render(<CaseIntelligencePage />);
        const views = screen.getByRole('group', { name: 'Case view' });
        expect(within(views).getByRole('button', { name: 'Cases' })).toHaveAttribute('aria-pressed', 'true');
        fireEvent.click(within(views).getByRole('button', { name: 'Case health' }));
        expect(await screen.findByText('Total cases')).toBeInTheDocument();
        expect(apiGetMock).toHaveBeenCalledWith('/api/admin/cases/health');
    });

    it('opens the first case beside the list on desktop and marks it selected', async () => {
        routeApi();
        render(<CaseIntelligencePage />);
        const list = await screen.findByRole('list', { name: 'Cases' });
        const rows = within(list).getAllByRole('button');
        expect(rows).toHaveLength(2);
        await waitFor(() => expect(rows[0]).toHaveAttribute('aria-current', 'true'));
        expect(rows[1]).not.toHaveAttribute('aria-current');
        const detail = await screen.findByRole('article');
        expect(within(detail).getByRole('heading', { name: 'Water Supply' })).toBeInTheDocument();
        expect(apiGetMock).toHaveBeenCalledWith('/api/admin/cases/1042');
        await waitFor(() => expect(replaceMock).toHaveBeenCalledWith('/dashboard/cases-intelligence/explorer?case=1042', { scroll: false }));
    });

    it('labels AI output separately from recorded facts and exposes no mutations', async () => {
        routeApi();
        render(<CaseIntelligencePage />);
        const detail = await screen.findByRole('article');
        const ai = await within(detail).findByRole('region', { name: 'Needle analysis' });
        expect(within(ai).getByText('AI-derived · not a staff decision')).toBeInTheDocument();
        expect(within(ai).getByText('Tap water outage in Kheda.')).toBeInTheDocument();
        expect(within(ai).getByText('Shadow — suggestion only, not applied')).toBeInTheDocument();
        expect(within(ai).getByText('Classifier asked for staff review')).toBeInTheDocument();
        expect(within(detail).getByText('Machine translation')).toBeInTheDocument();
        expect(within(detail).getByText('Assigned to').nextSibling).toHaveTextContent('kavya');

        const workspace = within(detail).getByRole('link', { name: 'Open in MP workspace →' });
        expect(workspace).toHaveAttribute('href', '/dashboard/mps/2#support');
        for (const name of [/update status/i, /reassign/i, /escalate/i, /add note/i, /accept category/i, /draft letter/i, /save/i, /delete/i]) {
            expect(screen.queryByRole('button', { name })).toBeNull();
        }
        expect(screen.queryByRole('textbox', { name: /note/i })).toBeNull();
        expect(apiPostMock).not.toHaveBeenCalled();
        expect(apiPatchMock).not.toHaveBeenCalled();
    });

    it('renders timeline, government, notes and messages tabs from real data only', async () => {
        routeApi();
        render(<CaseIntelligencePage />);
        const detail = await screen.findByRole('article');
        const tabs = await within(detail).findAllByRole('tab');
        expect(tabs.map((t) => t.textContent)).toEqual(['Overview', 'Timeline2', 'Government', 'Notes2', 'Messages2']);

        fireEvent.click(within(detail).getByRole('tab', { name: /Timeline/ }));
        expect(within(detail).getByText(/filed with government portal · ref PHED\/UDR\/412/i)).toBeInTheDocument();

        fireEvent.click(within(detail).getByRole('tab', { name: 'Government' }));
        expect(within(detail).getByText('Rajasthan Sampark · Rajasthan')).toBeInTheDocument();
        expect(within(detail).getByText('PHED/UDR/412')).toBeInTheDocument();

        fireEvent.click(within(detail).getByRole('tab', { name: /Notes/ }));
        expect(within(detail).getByText('Called the JE')).toBeInTheDocument();
        expect(within(detail).getByText(/read-only here/i)).toBeInTheDocument();

        fireEvent.click(within(detail).getByRole('tab', { name: /Messages/ }));
        expect(within(detail).getByText('We have registered your complaint.')).toBeInTheDocument();
        expect(within(detail).getByText('Citizen → Needle')).toBeInTheDocument();
    });

    it('shows only an overview when a case has no timeline, government, notes or messages', async () => {
        routeApi();
        render(<CaseIntelligencePage />);
        const list = await screen.findByRole('list', { name: 'Cases' });
        fireEvent.click(within(list).getAllByRole('button')[1]);
        const detail = await screen.findByRole('article');
        await within(detail).findByRole('heading', { name: 'Roads' });
        expect(within(detail).getAllByRole('tab').map((t) => t.textContent)).toEqual(['Overview']);
        expect(within(detail).queryByRole('region', { name: 'Needle analysis' })).toBeNull();
        expect(within(detail).getByText(/No staff or system activity has been logged/)).toBeInTheDocument();
        expect(within(detail).getByText('Unassigned')).toBeInTheDocument();
    });

    it('sends real filters to the explorer endpoint and honours tenant deep links', async () => {
        searchRef.current = 'tenant_id=3';
        routeApi();
        render(<CaseIntelligencePage />);
        await screen.findByRole('list', { name: 'Cases' });
        expect(apiGetMock).toHaveBeenCalledWith('/api/admin/cases/explorer?mp_id=3');
        expect(screen.getByRole('combobox', { name: 'Account' })).toHaveValue('3');

        fireEvent.click(screen.getByRole('tab', { name: 'Critical' }));
        await waitFor(() => expect(apiGetMock).toHaveBeenCalledWith('/api/admin/cases/explorer?mp_id=3&priority=critical'));
        fireEvent.change(screen.getByRole('combobox', { name: 'Status' }), { target: { value: 'new' } });
        await waitFor(() => expect(apiGetMock).toHaveBeenCalledWith('/api/admin/cases/explorer?mp_id=3&status=new&priority=critical'));
    });

    it('shows an error with retry when the explorer fails', async () => {
        routeApi({ '/api/admin/cases/explorer': new Error('Server unavailable') });
        render(<CaseIntelligencePage />);
        expect(await screen.findByText('Server unavailable')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
    });
});

describe('mobile master/detail', () => {
    it('leads with the list and opens a case sheet with Back to cases', async () => {
        setDesktop(false);
        routeApi();
        render(<CaseIntelligencePage />);
        const list = await screen.findByRole('list', { name: 'Cases' });
        expect(screen.queryByRole('article')).toBeNull();
        expect(apiGetMock).not.toHaveBeenCalledWith('/api/admin/cases/1042');

        fireEvent.click(within(list).getAllByRole('button')[0]);
        const sheet = await screen.findByRole('article');
        await within(sheet).findByRole('heading', { name: 'Water Supply' });
        fireEvent.click(within(sheet).getByRole('button', { name: 'Back to cases' }));
        await waitFor(() => expect(screen.queryByRole('article')).toBeNull());
        expect(within(list).getAllByRole('button')[0]).not.toHaveAttribute('aria-current');
    });
});
