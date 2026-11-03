import React, { createRef } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Delhi CM Jan Sunwai staff-assisted filing: staff file on the official portal,
// then record the reference via POST /api/cases/{id}/govt/manual-reference.
// Needle must never translate, auto-file, open a live session or check status
// for Delhi, and Karnataka/Maharashtra flows must stay exactly as they were.

const { apiGetMock, apiPostMock, toastMock } = vi.hoisted(() => ({
    apiGetMock: vi.fn(),
    apiPostMock: vi.fn(),
    toastMock: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

vi.mock('@/lib/api', () => ({
    apiGet: apiGetMock,
    apiPost: apiPostMock,
    apiPatch: vi.fn(),
    apiDelete: vi.fn(),
    API_BASE: 'http://api.test',
    getAuthToken: () => 'token',
}));
vi.mock('@/components/ui/toast', () => ({ useToast: () => toastMock }));

import DelhiManualReferencePanel, {
    DELHI_PORTAL_URL,
    isDelhiPortalState,
    isDelhiGovtCase,
    recordDelhiManualReference,
} from '@/components/briefcase/DelhiManualReferencePanel';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { GovtSyncSection, GovernmentJourneyPanel, delhiFiledCallout, ActivityTimeline } from '@/components/briefcase/BriefcaseCaseModal';

const httpError = (status, message) => Object.assign(new Error(message), { status });

beforeEach(() => {
    apiGetMock.mockReset();
    apiPostMock.mockReset();
    Object.values(toastMock).forEach((fn) => fn.mockReset());
});

describe('isDelhiPortalState', () => {
    it('matches Delhi only', () => {
        expect(isDelhiPortalState('Delhi')).toBe(true);
        expect(isDelhiPortalState(' delhi ')).toBe(true);
        for (const other of ['Karnataka', 'Maharashtra', 'Rajasthan', 'Tamil Nadu', 'Uttar Pradesh', '', null, undefined]) {
            expect(isDelhiPortalState(other)).toBe(false);
        }
    });
});

describe('recordDelhiManualReference', () => {
    it('sends only reference_number to the manual-reference endpoint', async () => {
        const post = vi.fn().mockResolvedValue({ success: true, govt_reference_number: '20260000001', status: 'in_progress' });
        const out = await recordDelhiManualReference(42, '  20260000001 ', post);
        expect(post).toHaveBeenCalledTimes(1);
        expect(post).toHaveBeenCalledWith('/api/cases/42/govt/manual-reference', { reference_number: '20260000001' });
        expect(out).toMatchObject({ kind: 'saved', reference: '20260000001' });
    });

    it('flags idempotent responses', async () => {
        const post = vi.fn().mockResolvedValue({ success: true, govt_reference_number: '20260000001', idempotent: true });
        expect((await recordDelhiManualReference(1, '20260000001', post)).kind).toBe('idempotent');
    });

    it('does not call the API for an empty reference', async () => {
        const post = vi.fn();
        expect((await recordDelhiManualReference(1, '   ', post)).kind).toBe('invalid');
        expect(post).not.toHaveBeenCalled();
    });

    it.each([
        [403, 'disabled'], [404, 'not_found'], [409, 'conflict'], [400, 'error'],
    ])('maps HTTP %s', async (status, kind) => {
        const post = vi.fn().mockRejectedValue(httpError(status, 'server detail'));
        expect((await recordDelhiManualReference(1, '20260000001', post)).kind).toBe(kind);
    });

    it('treats a network failure and an unconfirmed body as errors, never success', async () => {
        expect((await recordDelhiManualReference(1, '20260000001', vi.fn().mockRejectedValue(new Error('Failed to fetch')))).kind).toBe('error');
        expect((await recordDelhiManualReference(1, '20260000001', vi.fn().mockResolvedValue({ success: true }))).kind).toBe('error');
        expect((await recordDelhiManualReference(1, '20260000001', vi.fn().mockResolvedValue({}))).kind).toBe('error');
    });
});

describe('DelhiManualReferencePanel', () => {
    function type(value) {
        fireEvent.change(screen.getByLabelText('Delhi portal reference number'), { target: { value } });
    }

    it('explains staff-assisted filing and never claims automatic submission', () => {
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled govtCase={{}} />);
        const note = screen.getByTestId('delhi-honesty-note');
        expect(note).toHaveTextContent(/Staff-assisted filing/);
        expect(note).toHaveTextContent(/CAPTCHA and a one-time password \(OTP\) every time/);
        expect(note).toHaveTextContent(/does not submit anything to the portal and cannot read the portal's status/);
        expect(screen.getByRole('button', { name: 'Save reference' })).toBeDisabled();
    });

    it('opens only the official Delhi URL in a new tab', () => {
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled govtCase={{}} />);
        fireEvent.click(screen.getByRole('button', { name: 'Open official Delhi portal' }));
        expect(open).toHaveBeenCalledWith(DELHI_PORTAL_URL, '_blank', 'noopener,noreferrer');
        expect(DELHI_PORTAL_URL).toBe('https://cmjansunwai.delhi.gov.in/');
        expect(apiPostMock).not.toHaveBeenCalled();
    });

    it('shows success only after the backend confirms, then notifies once', async () => {
        let resolve;
        apiPostMock.mockReturnValue(new Promise((r) => { resolve = r; }));
        const onRecorded = vi.fn();
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled govtCase={{}} onRecorded={onRecorded} />);
        type('20260000009');
        fireEvent.click(screen.getByRole('button', { name: 'Save reference' }));
        expect(screen.queryByText(/saved/i)).not.toBeInTheDocument();   // nothing claimed while in flight
        expect(onRecorded).not.toHaveBeenCalled();
        await act(async () => { resolve({ success: true, govt_reference_number: '20260000009', status: 'in_progress' }); });
        expect(await screen.findByText(/Complaint number 20260000009 saved/)).toBeInTheDocument();
        expect(onRecorded).toHaveBeenCalledTimes(1);
        expect(onRecorded.mock.calls[0][0].kind).toBe('saved');
        expect(apiPostMock).toHaveBeenCalledWith('/api/cases/7/govt/manual-reference', { reference_number: '20260000009' });
    });

    it('reports an idempotent response as already recorded', async () => {
        apiPostMock.mockResolvedValue({ success: true, govt_reference_number: '20260000005', idempotent: true });
        const onRecorded = vi.fn();
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled govtCase={{}} onRecorded={onRecorded} />);
        type('20260000005');
        fireEvent.click(screen.getByRole('button', { name: 'Save reference' }));
        expect(await screen.findByText(/already recorded for this case/)).toBeInTheDocument();
        expect(onRecorded.mock.calls[0][0].kind).toBe('idempotent');
    });

    it.each([
        [403, /not enabled for this account/],
        [404, /could not be found/],
        [409, /already filed on the government portal \(reference DEL-OLD\)/],
    ])('shows a clear error for HTTP %s without claiming success', async (status, pattern) => {
        apiPostMock.mockRejectedValue(httpError(status, 'This case is already filed on the government portal (reference DEL-OLD).'));
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled govtCase={{}} />);
        type('20260000011');
        fireEvent.click(screen.getByRole('button', { name: 'Save reference' }));
        const alert = await screen.findByRole('alert');
        expect(alert.textContent).toMatch(pattern);
        expect(screen.queryByText(/marked as submitted/)).not.toBeInTheDocument();
    });

    it('shows a retryable error on network failure and keeps the typed reference', async () => {
        apiPostMock.mockRejectedValue(new Error('Failed to fetch'));
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled govtCase={{}} />);
        type('20260000012');
        fireEvent.click(screen.getByRole('button', { name: 'Save reference' }));
        expect((await screen.findByRole('alert')).textContent).toMatch(/Check your connection/);
        expect(screen.getByLabelText('Delhi portal reference number')).toHaveValue('20260000012');
    });

    it('shows the saved reference and submitted status, with no entry form, once filed', () => {
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled govtCase={{ govt_reference_number: 'DEL-77', govt_status: 'submitted' }} />);
        expect(screen.getByTestId('delhi-saved-reference')).toHaveTextContent('DEL-77');
        expect(screen.getByText(/Submitted \(recorded by staff\)/)).toBeInTheDocument();
        expect(screen.queryByLabelText('Delhi portal reference number')).not.toBeInTheDocument();
    });
});

// ─── GovtSyncSection wiring: Delhi vs Karnataka / Maharashtra ──────────────

const portalPayload = (state, portal) => ({ state, supported: true, live_automation_enabled: true, portal });
// Delhi's own row is inactive, so /api/govt-portal resolves a Delhi tenant to the CPGRAMS fallback.
const DELHI_PORTAL = { id: 9, portal_name: 'CPGRAMS', base_url: 'https://pgportal.gov.in', entry_url: 'https://pgportal.gov.in', otp_bound: false };
const DELHI_RESOLVED = { ...portalPayload('Delhi', DELHI_PORTAL), manual_reference_enabled: true };
const DELHI_DISABLED = { ...portalPayload('Delhi', DELHI_PORTAL), manual_reference_enabled: false };
const KARNATAKA_RESOLVED = portalPayload('Karnataka', { id: 2, portal_name: 'Karnataka Janaspandana (iPGRS)', base_url: 'https://ipgrs.karnataka.gov.in', entry_url: 'https://ipgrs.karnataka.gov.in', otp_bound: true });
const MAHARASHTRA_RESOLVED = portalPayload('Maharashtra', { id: 3, portal_name: 'Maharashtra Aaple Sarkar Grievance Redressal', base_url: 'https://grievances.maharashtra.gov.in', entry_url: 'https://grievances.maharashtra.gov.in', otp_bound: true });

function mockGovtApi(resolved, govtCase = { govt_status: 'not_forwarded' }) {
    apiGetMock.mockImplementation(async (path) => {
        if (path === '/api/govt-portal') return resolved;
        if (path.endsWith('/govt/history')) return null;
        if (path.endsWith('/govt')) return { case: govtCase };
        if (path === '/api/govt/sessions') return { sessions: [], global_count: 0, max_concurrent: 3 };
        return {};
    });
    apiPostMock.mockImplementation(async (path) => {
        if (path.endsWith('/govt/translate')) {
            return { worksheet: {}, portal: { portal_name: resolved.portal.portal_name } };
        }
        return { success: true };
    });
}

describe('capability visibility (manual_reference_enabled)', () => {
    it('panel without the capability shows an unavailable message, no entry form, no save action', () => {
        render(<DelhiManualReferencePanel caseId={7} govtCase={{}} manualReferenceEnabled={false} />);
        expect(screen.getByTestId('delhi-unavailable')).toHaveTextContent(/isn't available yet/);
        expect(screen.queryByLabelText('Delhi portal reference number')).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Save reference' })).not.toBeInTheDocument();
    });

    it('capability defaults to off when the prop is missing', () => {
        render(<DelhiManualReferencePanel caseId={7} govtCase={{}} />);
        expect(screen.getByTestId('delhi-unavailable')).toBeInTheDocument();
    });

    it('panel with the capability shows the entry form and no unavailable message', () => {
        render(<DelhiManualReferencePanel caseId={7} govtCase={{}} manualReferenceEnabled />);
        expect(screen.getByLabelText('Delhi portal reference number')).toBeInTheDocument();
        expect(screen.queryByTestId('delhi-unavailable')).not.toBeInTheDocument();
    });

    it('an already-recorded reference stays visible even when the capability is off', () => {
        render(<DelhiManualReferencePanel caseId={7} govtCase={{ govt_reference_number: '20260000001' }} manualReferenceEnabled={false} />);
        expect(screen.getByTestId('delhi-saved-reference')).toHaveTextContent('20260000001');
        expect(screen.queryByTestId('delhi-unavailable')).not.toBeInTheDocument();
    });

    it('GovtSyncSection reads the flag only from /api/govt-portal: disabled -> unavailable, enabled -> form', async () => {
        mockGovtApi(DELHI_DISABLED);
        const { unmount } = render(<GovtSyncSection caseId={5} isMp />);
        expect(await screen.findByTestId('delhi-unavailable')).toBeInTheDocument();
        expect(screen.queryByLabelText('Delhi portal reference number')).not.toBeInTheDocument();
        unmount();
        mockGovtApi(DELHI_RESOLVED);
        render(<GovtSyncSection caseId={5} isMp />);
        expect(await screen.findByLabelText('Delhi portal reference number')).toBeInTheDocument();
    });
});

describe('GovtSyncSection routing', () => {
    it('Delhi tenant gets the manual-reference panel, not the escalate/lock flow', async () => {
        mockGovtApi(DELHI_RESOLVED);
        render(<GovtSyncSection caseId={5} isMp />);
        expect(await screen.findByTestId('delhi-manual-reference')).toBeInTheDocument();
        expect(screen.queryByText(/available after staff escalates/)).not.toBeInTheDocument();
    });

    it('Delhi Escalate opens the official Delhi URL only - no translation, session or automated filing', async () => {
        mockGovtApi(DELHI_RESOLVED);
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        const ref = createRef();
        render(<GovtSyncSection ref={ref} caseId={5} isMp />);
        await screen.findByTestId('delhi-manual-reference');
        await act(async () => { await ref.current.openLiveSession(); });
        expect(open).toHaveBeenCalledWith('https://cmjansunwai.delhi.gov.in/', '_blank', 'noopener,noreferrer');
        expect(open).not.toHaveBeenCalledWith(expect.stringContaining('pgportal'), expect.anything(), expect.anything());
        expect(apiPostMock).not.toHaveBeenCalled();
    });

    it('Delhi status check does nothing automated', async () => {
        mockGovtApi(DELHI_RESOLVED);
        const ref = createRef();
        render(<GovtSyncSection ref={ref} caseId={5} isMp />);
        await screen.findByTestId('delhi-manual-reference');
        act(() => { ref.current.checkGovernmentStatus(); });
        expect(apiPostMock).not.toHaveBeenCalled();
        expect(toastMock.info).toHaveBeenCalled();
    });

    it('recording a Delhi reference calls only manual-reference, refreshes the case, and notifies once', async () => {
        const govtCase = { govt_status: 'not_forwarded' };
        mockGovtApi(DELHI_RESOLVED, govtCase);
        apiPostMock.mockResolvedValue({ success: true, govt_reference_number: '20260000001', status: 'in_progress' });
        const onSubmitted = vi.fn();
        render(<GovtSyncSection caseId={5} isMp onSubmitted={onSubmitted} />);
        await screen.findByTestId('delhi-manual-reference');
        // After the save the refreshed case carries the recorded reference.
        apiGetMock.mockImplementation(async (path) => {
            if (path.endsWith('/govt/history')) return null;
            if (path.endsWith('/govt')) return { case: { govt_status: 'submitted', govt_reference_number: '20260000001', govt_portal_id: 9 } };
            return DELHI_RESOLVED;
        });
        fireEvent.change(screen.getByLabelText('Delhi portal reference number'), { target: { value: '20260000001' } });
        fireEvent.click(screen.getByRole('button', { name: 'Save reference' }));
        await waitFor(() => expect(screen.getByTestId('delhi-saved-reference')).toHaveTextContent('20260000001'));
        expect(apiPostMock).toHaveBeenCalledTimes(1);
        expect(apiPostMock).toHaveBeenCalledWith('/api/cases/5/govt/manual-reference', { reference_number: '20260000001' });
        expect(onSubmitted).toHaveBeenCalledTimes(1);
        expect(onSubmitted).toHaveBeenCalledWith(5, 'in_progress');
    });

    it('an idempotent Delhi response does not notify the parent again', async () => {
        mockGovtApi(DELHI_RESOLVED);
        apiPostMock.mockResolvedValue({ success: true, govt_reference_number: '20260000001', idempotent: true });
        const onSubmitted = vi.fn();
        render(<GovtSyncSection caseId={5} isMp onSubmitted={onSubmitted} />);
        await screen.findByTestId('delhi-manual-reference');
        fireEvent.change(screen.getByLabelText('Delhi portal reference number'), { target: { value: '20260000001' } });
        fireEvent.click(screen.getByRole('button', { name: 'Save reference' }));
        await screen.findByText(/already recorded/);
        expect(onSubmitted).not.toHaveBeenCalled();
    });

    it.each([
        ['Karnataka', KARNATAKA_RESOLVED, 'https://ipgrs.karnataka.gov.in'],
        ['Maharashtra', MAHARASHTRA_RESOLVED, 'https://grievances.maharashtra.gov.in'],
    ])('%s is unchanged: no Delhi panel, Escalate opens its own portal and prepares the worksheet', async (_name, resolved, url) => {
        mockGovtApi(resolved);
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        const ref = createRef();
        render(<GovtSyncSection ref={ref} caseId={5} isMp />);
        expect(await screen.findByText(/available after staff escalates/)).toBeInTheDocument();
        expect(screen.queryByTestId('delhi-manual-reference')).not.toBeInTheDocument();
        await act(async () => { await ref.current.openLiveSession(); });
        expect(open).toHaveBeenCalledWith(url, '_blank', 'noopener,noreferrer');
        expect(apiPostMock).toHaveBeenCalledWith('/api/cases/5/govt/translate', {});
        expect(apiPostMock).not.toHaveBeenCalledWith(expect.stringContaining('manual-reference'), expect.anything());
    });
});


// ─── Action Panel / journey card: Delhi status is not integrated ────────────

const FILED_CASE = {
    id: 11, created_at: '2026-10-30T03:00:00Z', govt_status: 'submitted',
    govt_reference_number: 'DEL-77', portal_name: 'Delhi CM Jan Sunwai',
    govt_status_updated_at: '2026-10-30T04:00:00Z',
    latest_status_check: { checked_at: '2026-10-30T05:00:00Z', portal_detail: {} },
};

describe('delhiFiledCallout', () => {
    it('confirmed Delhi: says status is a staff task on the official portal, and never offers an automatic check', () => {
        const c = delhiFiledCallout();
        expect(c.text).toMatch(/checked by staff on the official portal/);
        expect(c.text).toMatch(/CAPTCHA and an OTP are needed each time/);
        expect(c.text).not.toMatch(/Check status to pull|Awaiting action/);
        expect(c.cta).toBeUndefined();           // no handler supplied -> no button
        const open = vi.fn();
        const withOpen = delhiFiledCallout({ onOpenTasks: open });
        expect(withOpen.cta).toBe('Open Delhi status steps');        // opens the staff-assisted steps...
        expect(withOpen.cta).not.toMatch(/Check government status/); // ...and is not the automatic-check wording
        withOpen.onAction();
        expect(open).toHaveBeenCalledTimes(1);
    });

});

describe('GovernmentJourneyPanel', () => {
    it('Delhi: hides Last checked and the refresh control, keeps reference and portal', () => {
        const onRefresh = vi.fn();
        render(<GovernmentJourneyPanel current={FILED_CASE} statusNotIntegrated onRefresh={onRefresh} />);
        expect(screen.queryByText('Last checked')).not.toBeInTheDocument();
        expect(screen.queryByTitle('Check government status')).not.toBeInTheDocument();
        expect(screen.getByText(/Grievance #DEL-77/)).toBeInTheDocument();
        expect(screen.getByText(/Delhi CM Jan Sunwai/)).toBeInTheDocument();
        expect(screen.getByText('Registered with Government portal')).toBeInTheDocument();
        expect(onRefresh).not.toHaveBeenCalled();
    });

    it('Delhi: replaces the department wording with the not-verified wording, keeps date', () => {
        render(<GovernmentJourneyPanel current={FILED_CASE} statusNotIntegrated />);
        expect(screen.getByText('Government department status')).toBeInTheDocument();
        expect(screen.getByText('Not verified by Needle')).toBeInTheDocument();
        expect(screen.getByText('Awaiting government response (not independently verified)')).toBeInTheDocument();
        expect(screen.queryByText('Awaiting department update')).not.toBeInTheDocument();
        expect(screen.queryByText('Currently with')).not.toBeInTheDocument();
        expect(screen.queryByText('Department action')).not.toBeInTheDocument();
        expect(screen.getAllByText('30 Oct')).toHaveLength(2);   // received + registered dates preserved
    });

    it.each([['Karnataka'], ['Maharashtra']])('%s: Last checked and the status-check control are unchanged', (_s) => {
        const onRefresh = vi.fn();
        render(<GovernmentJourneyPanel current={{ ...FILED_CASE, portal_name: `${_s} portal` }} onRefresh={onRefresh} />);
        expect(screen.getByText('Last checked')).toBeInTheDocument();
        expect(screen.getByText('Currently with')).toBeInTheDocument();
        expect(screen.getByText('Awaiting department update')).toBeInTheDocument();
        expect(screen.getByText('Department action')).toBeInTheDocument();
        expect(screen.queryByText(/not independently verified/)).not.toBeInTheDocument();
        expect(screen.queryByText('Government department status')).not.toBeInTheDocument();
        fireEvent.click(screen.getByTitle('Check government status'));
        expect(onRefresh).toHaveBeenCalledTimes(1);
    });
});

describe('isDelhiGovtCase (Delhi derived from the case row only - no extra request)', () => {
    it('is true only for a case linked to the Delhi portal', () => {
        expect(isDelhiGovtCase({ govt_portal_name: 'Delhi CM Jan Sunwai' })).toBe(true);
        expect(isDelhiGovtCase({ portal_name: ' Delhi CM Jan Sunwai ' })).toBe(true);
        expect(isDelhiGovtCase(FILED_CASE)).toBe(true);
    });
    it.each([
        [null], [undefined], [{}], [{ govt_portal_name: null }], [{ govt_portal_name: '' }],
        [{ govt_portal_name: 'Karnataka Janaspandana (iPGRS)' }], [{ govt_portal_name: 'Maharashtra Aaple Sarkar' }],
        [{ portal_name: 'CPGRAMS' }], [{ govt_portal_name: 'Delhi' }],
    ])('is false (original presentation kept) for %j', (c) => { expect(isDelhiGovtCase(c)).toBe(false); });
    it('prefers the stable portal state over the display name', () => {
        expect(isDelhiGovtCase({ govt_portal_state: 'Delhi', govt_portal_name: 'Renamed portal' })).toBe(true);
        expect(isDelhiGovtCase({ govt_portal_state: ' delhi ' })).toBe(true);
        expect(isDelhiGovtCase({ portal_state: 'Delhi' })).toBe(true);
        expect(isDelhiGovtCase({ govt_portal_state: 'Karnataka', govt_portal_name: 'Delhi CM Jan Sunwai' })).toBe(false);
        expect(isDelhiGovtCase({ govt_portal_state: '', govt_portal_name: 'Delhi CM Jan Sunwai' })).toBe(true);
        expect(isDelhiGovtCase({ govt_portal_state: null })).toBe(false);
    });
});

describe('modal wiring pins', () => {
    const src = readFileSync(join(process.cwd(), 'components/briefcase/BriefcaseCaseModal.jsx'), 'utf8');
    it('derives Delhi from the case row and feeds both the callout and the journey card', () => {
        expect(src).toContain('const isDelhiFiledCase = isDelhiGovtCase(current);');
        expect(src).toContain('if (isDelhiFiledCase) return delhiFiledCallout(');
        expect(src).toContain('statusNotIntegrated={isDelhiFiledCase}');
    });
    it('non-Delhi portals keep the original callout wording and Check government status action verbatim', () => {
        expect(src).toContain("text: `Awaiting action from ${current.govt_department || 'the department'}. Use Check status to pull the latest portal update.`,");
        expect(src).toContain("cta: 'Check government status', onAction: handleGovernmentStatusClick");
        expect(src.indexOf('if (isDelhiFiledCase) return delhiFiledCallout(')).toBeLessThan(src.indexOf("cta: 'Check government status', onAction: handleGovernmentStatusClick"));
    });
    it('does not carry the shared portal-identity / fail-closed behaviour (kept out of the Delhi change set)', () => {
        expect(src).not.toContain('useGovtPortalIdentity');
        expect(src).not.toContain('portalLookupFailed');
        expect(src).not.toContain('govt-portal-lookup-failed');
        expect(src).not.toContain('resolvedPortal == null');
        expect(src).not.toContain('loadResolvedPortal');
        // no new /api/govt-portal request: the same two pre-existing call sites as at the base commit
        expect(src.match(/apiGet\('\/api\/govt-portal'\)/g)).toHaveLength(2);
    });
});


// ─── Filing-section lookup failure / retry / in-flight race ─────────────────

function mockGovtApiWithPortal(portalHandler, govtCase = { govt_status: 'not_forwarded' }) {
    apiGetMock.mockImplementation(async (path) => {
        if (path === '/api/govt-portal') return portalHandler();
        if (path.endsWith('/govt/history')) return null;
        if (path.endsWith('/govt')) return { case: govtCase };
        if (path === '/api/govt/sessions') return { sessions: [], global_count: 0, max_concurrent: 3 };
        return {};
    });
    apiPostMock.mockImplementation(async (path) => (
        path.endsWith('/govt/translate') ? { worksheet: {}, portal: { portal_name: 'x' } } : { success: true }
    ));
}

const noGenericFilingPosts = () => {
    const paths = apiPostMock.mock.calls.map(([path]) => path);
    expect(paths.filter((x) => /translate|session|poll|status-check|\/govt\/submit/.test(x))).toEqual([]);
};

describe('GovtSyncSection: Delhi routing is not bypassed by a fast click, and other portals are unchanged', () => {
    it('in-flight race: a click while the lookup is pending, later resolving to Delhi, opens only the Delhi URL', async () => {
        let resolveLookup;
        mockGovtApiWithPortal(() => new Promise((r) => { resolveLookup = r; }));
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        const ref = createRef();
        render(<GovtSyncSection ref={ref} caseId={5} isMp />);
        // Lookup still pending: the generic locked view is visible, so click its Escalate button.
        const escalate = await screen.findByRole('button', { name: /Escalate to proceed/ });
        await act(async () => { fireEvent.click(escalate); });
        expect(open).not.toHaveBeenCalled();
        await act(async () => { resolveLookup(DELHI_RESOLVED); });
        await waitFor(() => expect(open).toHaveBeenCalledTimes(1));
        expect(open).toHaveBeenCalledWith('https://cmjansunwai.delhi.gov.in/', '_blank', 'noopener,noreferrer');
        expect(open).not.toHaveBeenCalledWith(expect.stringContaining('pgportal'), expect.anything(), expect.anything());
        noGenericFilingPosts();
    });

    it('in-flight race via the Action Panel path (openLiveSession) is equally protected', async () => {
        let resolveLookup;
        mockGovtApiWithPortal(() => new Promise((r) => { resolveLookup = r; }));
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        const ref = createRef();
        render(<GovtSyncSection ref={ref} caseId={5} isMp />);
        await screen.findByRole('button', { name: /Escalate to proceed/ });
        let pending;
        act(() => { pending = ref.current.openLiveSession(); });
        await act(async () => { resolveLookup(DELHI_RESOLVED); await pending; });
        expect(open).toHaveBeenCalledTimes(1);
        expect(open).toHaveBeenCalledWith('https://cmjansunwai.delhi.gov.in/', '_blank', 'noopener,noreferrer');
        noGenericFilingPosts();
    });

    it('the Escalate locked button, while the lookup is pending and resolves to Karnataka, behaves as before', async () => {
        let resolveLookup;
        mockGovtApiWithPortal(() => new Promise((r) => { resolveLookup = r; }));
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        render(<GovtSyncSection caseId={5} isMp />);
        const escalate = await screen.findByRole('button', { name: /Escalate to proceed/ });
        await act(async () => { fireEvent.click(escalate); });
        await act(async () => { resolveLookup(KARNATAKA_RESOLVED); });
        await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith('/api/cases/5/govt/translate', {}));
        expect(open).toHaveBeenCalledWith('https://ipgrs.karnataka.gov.in', '_blank', 'noopener,noreferrer');
    });

    it.each([
        ['Karnataka', KARNATAKA_RESOLVED, 'https://ipgrs.karnataka.gov.in'],
        ['Maharashtra', MAHARASHTRA_RESOLVED, 'https://grievances.maharashtra.gov.in'],
    ])('confirmed %s: locked Escalate button works through both entry points with its own URL and translation', async (_n, resolved, url) => {
        mockGovtApiWithPortal(() => resolved);
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        const ref = createRef();
        render(<GovtSyncSection ref={ref} caseId={5} isMp />);
        fireEvent.click(await screen.findByRole('button', { name: /Escalate to proceed/ }));
        await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith('/api/cases/5/govt/translate', {}));
        expect(open).toHaveBeenLastCalledWith(url, '_blank', 'noopener,noreferrer');
        apiPostMock.mockClear(); open.mockClear();
        await act(async () => { await ref.current.openLiveSession(); });
        expect(open).toHaveBeenCalledWith(url, '_blank', 'noopener,noreferrer');
        expect(apiPostMock).toHaveBeenCalledWith('/api/cases/5/govt/translate', {});
        expect(toastMock.error).not.toHaveBeenCalled();
    });

    it('an already-filed case with a failed lookup keeps its original reference presentation', async () => {
        mockGovtApiWithPortal(() => { throw new Error('boom'); }, { govt_status: 'submitted', govt_reference_number: 'REF-9', govt_portal_id: 4 });
        render(<GovtSyncSection caseId={5} isMp />);
        expect(await screen.findByText('REF-9')).toBeInTheDocument();
    });
});

// ─── Staff-assisted Delhi workflow (worksheet, filing steps, reference rule, status/reminder/feedback tasks) ───
import {
    DELHI_REFERENCE_RE, prepareDelhiWorksheet, logDelhiTask,
} from '@/components/briefcase/DelhiManualReferencePanel';

const BASE = 'https://cmjansunwai.delhi.gov.in';
const TASKS = [
    { key: 'file', label: 'File the complaint', url: `${BASE}/`, available: 'before a complaint number is recorded', automation: 'none',
      steps: ['On the portal home page choose Complaint Registration.', 'Enter the mobile number and the CAPTCHA, then the OTP.'],
      inputs: ['mobile number (10 digits)', 'image CAPTCHA (6 characters)', 'one-time password (OTP, 6 digits)'] },
    { key: 'status', label: 'Check status on the portal', url: `${BASE}/ComplaintTracker`, available: 'after the complaint number is recorded', automation: 'none',
      steps: ['Open the official Complaint Status page.'], inputs: ['complaint number (numeric, up to 14 digits)', 'registered mobile number (10 digits) or e-mail ID', 'image CAPTCHA (6 characters)', 'one-time password (OTP, 6 digits)'] },
    { key: 'reminder', label: 'Send a reminder', url: `${BASE}/SendReminder`, available: 'after the complaint number is recorded', automation: 'none', steps: ['x'], inputs: ['complaint number', 'CAPTCHA', 'OTP'] },
    { key: 'feedback', label: 'Give feedback on a disposed complaint', url: `${BASE}/onlineFeedbackEntry`, available: 'only after the portal shows the complaint as disposed', automation: 'none', steps: ['x'], inputs: ['complaint number', 'CAPTCHA', 'OTP'] },
];
const WS = { subject: 'Water supply failure in Ward 5', description: 'Residents report no water for three days.', department: null,
             department_note: 'Department/category not chosen by Needle: the portal\'s options are not public. Pick it on the portal.', limits_note: 'Soft drafting targets only.' };
const GENERIC_AUTOMATION = /govt\/(translate|session|poll|status-check|submit)\b/;

describe('Delhi reference rule (client side, same as the portal\'s own tracker)', () => {
    it.each(['DEL-1', 'abc', '12 34', '123456789012345', '1e5', '٣٤٥', '12.5'])('rejects %s without calling the API', async (bad) => {
        const post = vi.fn();
        expect((await recordDelhiManualReference(1, bad, post)).kind).toBe('invalid');
        expect(post).not.toHaveBeenCalled();
    });
    it.each(['1', '12345678901234', '00012345'])('accepts %s', (ok) => { expect(DELHI_REFERENCE_RE.test(ok)).toBe(true); });
});

describe('prepareDelhiWorksheet / logDelhiTask', () => {
    it('prepare: confirmed draft -> prepared; only the prepare endpoint is called', async () => {
        const post = vi.fn().mockResolvedValue({ success: true, worksheet: WS, portal_contact_number: '9000000001' });
        const out = await prepareDelhiWorksheet(7, post);
        expect(out).toMatchObject({ kind: 'prepared', contactNumber: '9000000001' });
        expect(post).toHaveBeenCalledTimes(1);
        expect(post).toHaveBeenCalledWith('/api/cases/7/govt/delhi/prepare-worksheet', {});
        expect(post.mock.calls[0][0]).not.toMatch(GENERIC_AUTOMATION);
    });
    it.each([[403, 'disabled'], [404, 'not_found'], [409, 'conflict'], [502, 'error'], [400, 'error']])('prepare maps HTTP %s', async (status, kind) => {
        expect((await prepareDelhiWorksheet(7, vi.fn().mockRejectedValue(httpError(status, 'detail')))).kind).toBe(kind);
    });
    it('prepare: network failure and an unconfirmed/empty draft are errors, never success', async () => {
        expect((await prepareDelhiWorksheet(7, vi.fn().mockRejectedValue(new Error('Failed to fetch')))).kind).toBe('error');
        expect((await prepareDelhiWorksheet(7, vi.fn().mockResolvedValue({ success: true, worksheet: { subject: '', description: 'x' } }))).kind).toBe('error');
        expect((await prepareDelhiWorksheet(7, vi.fn().mockResolvedValue({}))).kind).toBe('error');
    });
    it('task log: sends only the task key; maps 409 (number not recorded yet)', async () => {
        const post = vi.fn().mockResolvedValue({ success: true, task: TASKS[1] });
        expect((await logDelhiTask(7, 'status', post)).kind).toBe('logged');
        expect(post).toHaveBeenCalledWith('/api/cases/7/govt/delhi/task', { task: 'status' });
        expect((await logDelhiTask(7, 'status', vi.fn().mockRejectedValue(httpError(409, 'Record the Delhi complaint number first')))).kind).toBe('conflict');
    });
});

describe('DelhiManualReferencePanel: staff-assisted workflow', () => {
    it('drafts the worksheet through the Delhi endpoint only, shows subject/description and never a department', async () => {
        apiPostMock.mockResolvedValue({ success: true, worksheet: WS, portal_contact_number: '9000000001' });
        const onRecorded = vi.fn();
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled tasks={TASKS} govtCase={{}} onRecorded={onRecorded} />);
        fireEvent.click(screen.getByRole('button', { name: 'Draft worksheet with AI' }));
        expect(await screen.findByTestId('delhi-ws-subject')).toHaveTextContent('Water supply failure in Ward 5');
        expect(screen.getByTestId('delhi-ws-description')).toHaveTextContent('no water for three days');
        expect(screen.getByTestId('delhi-ws-notes')).toHaveTextContent(/not chosen by Needle/);
        expect(screen.queryByText(/^Department$/i)).not.toBeInTheDocument();
        expect(screen.getByTestId('delhi-contact')).toHaveTextContent('9000000001');
        expect(apiPostMock).toHaveBeenCalledTimes(1);
        expect(apiPostMock.mock.calls[0][0]).toBe('/api/cases/7/govt/delhi/prepare-worksheet');
        expect(apiPostMock.mock.calls.every(([p]) => !GENERIC_AUTOMATION.test(p))).toBe(true);
        expect(onRecorded).toHaveBeenCalledWith({ kind: 'prepared' });
        expect(screen.getByText(/Nothing has been sent to the portal/)).toBeInTheDocument();
    });

    it('shows a draft that already exists on the case after a reload', () => {
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled tasks={TASKS} govtCase={{ govt_submission_worksheet: WS }} />);
        expect(screen.getByTestId('delhi-ws-subject')).toHaveTextContent('Water supply failure in Ward 5');
        expect(screen.getByRole('button', { name: 'Draft again' })).toBeInTheDocument();
    });

    it('shows the server-provided filing steps and opens ONLY the official portal, then audits the task', async () => {
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        apiPostMock.mockResolvedValue({ success: true, task: TASKS[0] });
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled tasks={TASKS} govtCase={{}} />);
        expect(screen.getByTestId('delhi-file-steps')).toHaveTextContent('choose Complaint Registration');
        fireEvent.click(screen.getByRole('button', { name: 'Open official Delhi portal' }));
        expect(open).toHaveBeenCalledWith(`${BASE}/`, '_blank', 'noopener,noreferrer');
        await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith('/api/cases/7/govt/delhi/task', { task: 'file' }));
        expect(apiPostMock.mock.calls.every(([p]) => !GENERIC_AUTOMATION.test(p))).toBe(true);
    });

    it('with no server tasks nothing is hard-coded: file still opens the official URL, no task cards appear', () => {
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled govtCase={{}} />);
        expect(screen.queryByTestId('delhi-file-steps')).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Open official Delhi portal' }));
        expect(open).toHaveBeenCalledWith('https://cmjansunwai.delhi.gov.in/', '_blank', 'noopener,noreferrer');
    });

    it('rejects a non-numeric complaint number in the UI without a request', async () => {
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled tasks={TASKS} govtCase={{}} />);
        fireEvent.change(screen.getByLabelText('Delhi portal reference number'), { target: { value: 'DEL/2026/5' } });
        fireEvent.click(screen.getByRole('button', { name: 'Save reference' }));
        expect((await screen.findByRole('alert')).textContent).toMatch(/numeric, up to 14 digits/);
        expect(apiPostMock).not.toHaveBeenCalled();
    });

    it('once filed: status / reminder / feedback tasks appear with the exact inputs the portal asks for, and no automatic-status claim', () => {
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled tasks={TASKS} govtCase={{ govt_reference_number: '20260000123', govt_status: 'submitted' }} />);
        for (const k of ['status', 'reminder', 'feedback']) expect(screen.getByTestId(`delhi-task-${k}`)).toBeInTheDocument();
        expect(screen.getByTestId('delhi-task-status')).toHaveTextContent(/image CAPTCHA/);
        expect(screen.getByTestId('delhi-task-status')).toHaveTextContent(/one-time password/);
        expect(screen.getByTestId('delhi-task-feedback')).toHaveTextContent(/only after the portal shows the complaint as disposed/);
        expect(screen.queryByTestId('delhi-step-prepare')).not.toBeInTheDocument();     // no re-drafting after filing
        expect(screen.queryByLabelText('Delhi portal reference number')).not.toBeInTheDocument();
        expect(screen.getByText(/does not check Delhi status automatically/)).toBeInTheDocument();
    });

    it.each([['status', '/ComplaintTracker'], ['reminder', '/SendReminder'], ['feedback', '/onlineFeedbackEntry']])('%s task opens the official page and is audited', async (key, path) => {
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        apiPostMock.mockResolvedValue({ success: true, task: TASKS.find((t) => t.key === key) });
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled tasks={TASKS} govtCase={{ govt_reference_number: '20260000123' }} />);
        fireEvent.click(within(screen.getByTestId(`delhi-task-${key}`)).getByRole('button'));
        expect(open).toHaveBeenCalledWith(`${BASE}${path}`, '_blank', 'noopener,noreferrer');
        await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith('/api/cases/7/govt/delhi/task', { task: key }));
        expect(apiPostMock).toHaveBeenCalledTimes(1);
    });

    it('a failed task audit is reported clearly (the page still opened; nothing is claimed)', async () => {
        vi.spyOn(window, 'open').mockImplementation(() => null);
        apiPostMock.mockRejectedValue(httpError(409, 'Record the Delhi complaint number on this case first - this task needs it.'));
        render(<DelhiManualReferencePanel caseId={7} manualReferenceEnabled tasks={TASKS} govtCase={{ govt_reference_number: '20260000123' }} />);
        fireEvent.click(within(screen.getByTestId('delhi-task-status')).getByRole('button'));
        expect((await screen.findByRole('alert')).textContent).toMatch(/complaint number/i);
    });
});

describe('GovtSyncSection: Delhi staff-assisted flow end to end (mocked backend)', () => {
    const DELHI_FULL = { ...DELHI_RESOLVED, staff_assisted_tasks: TASKS, portal_contact_number: '9000000001' };

    it('draft -> opens the portal -> record the number -> tasks appear; no generic automation endpoint is ever called', async () => {
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        let filed = false;
        apiGetMock.mockImplementation(async (path) => {
            if (path === '/api/govt-portal') return DELHI_FULL;
            if (path.endsWith('/govt/history')) return null;
            if (path.endsWith('/govt')) return { case: filed ? { govt_status: 'submitted', govt_reference_number: '20260000123', govt_portal_id: 9 } : { govt_status: 'not_forwarded' } };
            if (path === '/api/govt/sessions') return { sessions: [], global_count: 0, max_concurrent: 3 };
            return {};
        });
        apiPostMock.mockImplementation(async (path) => {
            if (path.endsWith('/delhi/prepare-worksheet')) return { success: true, worksheet: WS, portal_contact_number: '9000000001' };
            if (path.endsWith('/delhi/task')) return { success: true, task: TASKS[0] };
            if (path.endsWith('/manual-reference')) { filed = true; return { success: true, govt_reference_number: '20260000123', status: 'in_progress' }; }
            throw new Error(`unexpected POST ${path}`);
        });
        const onSubmitted = vi.fn();
        render(<GovtSyncSection caseId={5} isMp onSubmitted={onSubmitted} />);
        fireEvent.click(await screen.findByRole('button', { name: 'Draft worksheet with AI' }));
        expect(await screen.findByTestId('delhi-ws-subject')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Open official Delhi portal' }));
        expect(open).toHaveBeenCalledWith(`${BASE}/`, '_blank', 'noopener,noreferrer');
        fireEvent.change(screen.getByLabelText('Delhi portal reference number'), { target: { value: '20260000123' } });
        fireEvent.click(screen.getByRole('button', { name: 'Save reference' }));
        await waitFor(() => expect(screen.getByTestId('delhi-saved-reference')).toHaveTextContent('20260000123'));
        expect(screen.getByTestId('delhi-task-status')).toBeInTheDocument();
        expect(onSubmitted).toHaveBeenCalledTimes(1);
        const paths = apiPostMock.mock.calls.map(([p]) => p);
        expect(paths.filter((p) => GENERIC_AUTOMATION.test(p) && !p.endsWith('/manual-reference'))).toEqual([]);
        expect(paths).toContain('/api/cases/5/govt/delhi/prepare-worksheet');
    });

    it('Delhi Escalate (Action Panel path) still opens only the official Delhi URL and prepares nothing', async () => {
        const open = vi.spyOn(window, 'open').mockImplementation(() => null);
        mockGovtApiWithPortal(() => DELHI_FULL);
        const ref = createRef();
        render(<GovtSyncSection ref={ref} caseId={5} isMp />);
        await screen.findByTestId('delhi-manual-reference');
        await act(async () => { await ref.current.openLiveSession(); });
        expect(open).toHaveBeenCalledWith('https://cmjansunwai.delhi.gov.in/', '_blank', 'noopener,noreferrer');
        expect(apiPostMock).not.toHaveBeenCalled();
    });
});

describe('ActivityTimeline: Delhi staff actions are readable', () => {
    it('labels the Delhi events and leaves other actions unchanged', () => {
        render(<ActivityTimeline loading={false} activities={[
            { id: 1, action: 'govt_delhi_worksheet_drafted', created_at: '2026-10-31T09:00:00Z', username: 'a' },
            { id: 2, action: 'govt_delhi_task', new_value: 'status', created_at: '2026-10-31T09:05:00Z', username: 'a' },
            { id: 3, action: 'govt_submitted', new_value: '20260000123', created_at: '2026-10-31T09:03:00Z', username: 'a' },
        ]} />);
        expect(screen.getByText(/Delhi complaint worksheet drafted \(AI\) — nothing sent to the portal/)).toBeInTheDocument();
        expect(screen.getByText(/Staff opened the official Delhi portal to check status/)).toBeInTheDocument();
        expect(screen.getByText(/govt submitted → 20260000123/)).toBeInTheDocument();
    });
});
