import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Delhi filing worksheet (synthetic data, injected API functions): department / category / location selection,
// incomplete-catalogue handling, verified limits, PDF pre-check, AI-suggestion vs staff-selection provenance and the
// "saved is not filed" wording. Nothing here contacts the Delhi portal.

vi.mock('@/lib/api', () => ({
    apiGet: vi.fn(),
    apiPost: vi.fn(),
    apiPatch: vi.fn(),
    apiDelete: vi.fn(),
    API_BASE: 'http://api.test',
    getAuthToken: () => 'token',
}));

import DelhiFilingWorksheet, {
    checkDelhiAttachment,
    fetchDelhiCatalogue,
    fetchDelhiCategories,
    saveDelhiFilingWorksheet,
    suggestDelhiDepartment,
} from '@/components/briefcase/DelhiFilingWorksheet';

const httpError = (status, message) => Object.assign(new Error(message), { status });

const RULES = {
    address_max_chars: 250,
    grievance_details: { portal_max_chars: null, portal_max_verified: false, soft_warn_chars: 1500, special_chars_notice: 'NOTICE: avoid special characters; no character is rejected by Needle.' },
    attachment: { content_type: 'application/pdf', extension: '.pdf', max_bytes: 1048576, max_name_chars: 99, forbidden_name_chars: '<>`=\'~%"*^$&#' },
};
const DEPARTMENTS = [
    { name: 'Delhi Police', categories_status: 'captured_partial_verification', category_count: 3, categories_complete: true, form_comparison: 'pending' },
    { name: 'Some Uncaptured Department', categories_status: 'not_captured', category_count: 0, categories_complete: false, form_comparison: 'pending' },
    { name: 'Partial Department', categories_status: 'captured_partial_verification', capture_status: 'partial', category_count: 2, categories_complete: false, unverified_row_count: 1, form_comparison: 'pending' },
];
const PARTIAL = {
    department: 'Partial Department', categories_complete: false, capture_status: 'partial', unverified_row_count: 1, form_comparison: 'pending',
    categories: [
        { seq: 1, text: 'Zeta first', verification: 'page_text_exact', l1: { post: 'a', disposal_days: 21 }, l2: { post: 'b', disposal_days: 10 }, l3: { post: 'c', disposal_days: 10 } },
        { seq: 2, text: 'Alpha &amp;amp; second', verification: 'screenshot_repaired_not_text_verified', l1: { post: 'a', disposal_days: 21 }, l2: { post: 'b', disposal_days: 10 }, l3: { post: 'c', disposal_days: 10 } },
    ],
};
const POLICE = {
    department: 'Delhi Police', categories_complete: true, form_comparison: 'pending',
    categories: [
        { seq: 1, text: 'Abuse of Power', l1: { post: 'L1 post', disposal_days: 21 }, l2: { post: 'L2 post', disposal_days: 10 }, l3: { post: 'L3 post', disposal_days: 10 } },
        { seq: 2, text: 'Corruption', l1: { post: 'a', disposal_days: 21 }, l2: { post: 'b', disposal_days: 10 }, l3: { post: 'c', disposal_days: 10 } },
        { seq: 3, text: 'Trafffic jam (portal spelling)', l1: { post: 'a', disposal_days: 21 }, l2: { post: 'b', disposal_days: 10 }, l3: { post: 'c', disposal_days: 10 } },
    ],
};
const UNCAPTURED = { department: 'Some Uncaptured Department', categories_complete: false, form_comparison: 'pending', categories: [] };

function makeGet({ catalogueFails = false } = {}) {
    return vi.fn(async (path) => {
        if (path === '/api/govt/delhi/catalogue') {
            if (catalogueFails) throw httpError(500, 'boom');
            return { meta: {}, departments: DEPARTMENTS, field_rules: RULES };
        }
        if (path.includes('department=Delhi%20Police')) return POLICE;
        if (path.includes('Some%20Uncaptured%20Department')) return UNCAPTURED;
        if (path.includes('department=Partial%20Department')) return PARTIAL;
        throw httpError(404, 'nope');
    });
}

const okSave = (over = {}) => ({
    success: true,
    saved: { selection_sources: { department: 'staff_confirmed', category: 'staff_confirmed', location: 'staff_typed_unverified' } },
    validation: { ok: true, ready_to_file: true, errors: [], warnings: [], notices: [{ field: 'grievance_details', code: 'special_characters_note', message: RULES.grievance_details.special_chars_notice }] },
    ...over,
});

async function renderWs({ get = makeGet(), post = vi.fn(), govtCase = null, ai = '', onSaved = vi.fn() } = {}) {
    const utils = render(<DelhiFilingWorksheet caseId={7} govtCase={govtCase} aiDraftDescription={ai} getFn={get} postFn={post} onSaved={onSaved} />);
    await waitFor(() => expect(get).toHaveBeenCalledWith('/api/govt/delhi/catalogue'));
    await act(async () => {});
    return { ...utils, get, post, onSaved };
}
const type = (label, value) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

beforeEach(() => { vi.restoreAllMocks(); });

describe('API helpers', () => {
    it('fetchDelhiCatalogue returns departments + rules and maps failures', async () => {
        expect((await fetchDelhiCatalogue(makeGet())).kind).toBe('loaded');
        expect((await fetchDelhiCatalogue(vi.fn().mockResolvedValue({}))).kind).toBe('error');
        expect((await fetchDelhiCatalogue(vi.fn().mockRejectedValue(httpError(403, 'x')))).kind).toBe('disabled');
        expect((await fetchDelhiCatalogue(vi.fn().mockRejectedValue(new Error('net')))).kind).toBe('error');
    });
    it('fetchDelhiCategories URL-encodes the exact department name', async () => {
        const get = vi.fn().mockResolvedValue(POLICE);
        await fetchDelhiCategories('Delhi Police', get);
        expect(get).toHaveBeenCalledWith('/api/govt/delhi/catalogue/categories?department=Delhi%20Police');
        expect((await fetchDelhiCategories('x', vi.fn().mockResolvedValue({}))).kind).toBe('error');
    });
    it('saveDelhiFilingWorksheet posts to the worksheet endpoint and requires a confirmed response', async () => {
        const post = vi.fn().mockResolvedValue(okSave());
        const out = await saveDelhiFilingWorksheet(7, { department: 'Delhi Police' }, post);
        expect(post).toHaveBeenCalledWith('/api/cases/7/govt/delhi/filing-worksheet', { department: 'Delhi Police' });
        expect(out.kind).toBe('saved');
        expect((await saveDelhiFilingWorksheet(7, {}, vi.fn().mockResolvedValue({ success: true }))).kind).toBe('error');
        expect((await saveDelhiFilingWorksheet(7, {}, vi.fn().mockRejectedValue(httpError(409, 'already filed')))).kind).toBe('conflict');
    });
    it('suggestDelhiDepartment maps 502 to a friendly error', async () => {
        const out = await suggestDelhiDepartment(7, vi.fn().mockRejectedValue(httpError(502, 'x')));
        expect(out.kind).toBe('error');
        expect(out.message).toMatch(/choose the department yourself/i);
    });
});

describe('checkDelhiAttachment (verified rules only)', () => {
    const f = (name, size = 100, type = 'application/pdf') => ({ name, size, type });
    it('accepts a normal PDF', () => expect(checkDelhiAttachment(f('proof_1.pdf'), RULES)).toEqual([]));
    it.each([
        [f('proof.docx', 100, 'application/msword'), /Only PDF/],
        [f('proof.pdf', 1048577), /1 MB/],
        [f('my proof.pdf'), /spaces/],
        [f('proof(1).pdf'), /parentheses/],
        [f('proof..pdf'), /“\.\.”/],
        [f('pro#of.pdf'), /does not allow/],
        [f(`${'a'.repeat(96)}.pdf`), /shorter than 100/],
    ])('rejects %#', (file, re) => {
        expect(checkDelhiAttachment(file, RULES).join(' ')).toMatch(re);
    });
    it('does nothing without rules or a file', () => {
        expect(checkDelhiAttachment(null, RULES)).toEqual([]);
        expect(checkDelhiAttachment(f('a.pdf'), null)).toEqual([]);
    });
});

describe('DelhiFilingWorksheet', () => {
    it('lists the catalogue departments and says nothing is sent to the portal', async () => {
        await renderWs();
        const opts = [...document.querySelectorAll('#delhi-fw-departments option')].map((o) => o.value);
        expect(opts).toEqual(['Delhi Police', 'Some Uncaptured Department', 'Partial Department']);
        expect(screen.getByText(/does not fill in or submit the portal form/i)).toBeTruthy();
        expect(screen.getByText(/Mobile No\. 1 is pre-filled by the portal/i)).toBeTruthy();
    });

    it('loads the captured categories for a department and shows the escalation chain and days', async () => {
        await renderWs();
        type(/Department \*/, 'Delhi Police');
        await waitFor(() => expect(screen.getByTestId('delhi-fw-dept-status').textContent).toMatch(/holds 3 categories/));
        expect(screen.getByTestId('delhi-fw-dept-status').textContent).toMatch(/not yet compared with the filing form/);
        const cats = [...document.querySelectorAll('#delhi-fw-categories option')].map((o) => o.value);
        expect(cats).toEqual(['Abuse of Power', 'Corruption', 'Trafffic jam (portal spelling)']);   // order and spelling preserved
        type(/Grievance Category \*/, 'Abuse of Power');
        const chain = screen.getByTestId('delhi-fw-escalation').textContent;
        expect(chain).toMatch(/L1: L1 post · 21 days/);
        expect(chain).toMatch(/L2: L2 post · 10 days/);
        expect(screen.getByTestId('delhi-fw-source-category').textContent).toMatch(/Chosen from Needle’s copy/);
    });

    it('an uncaptured department does not block filing: it says so and accepts a typed category', async () => {
        await renderWs();
        type(/Department \*/, 'Some Uncaptured Department');
        await waitFor(() => expect(screen.getByTestId('delhi-fw-dept-status').textContent).toMatch(/has not captured/));
        expect(screen.getByTestId('delhi-fw-dept-status').textContent).toMatch(/Filing is not blocked/);
        type(/Grievance Category \*/, 'Typed as shown on portal');
        expect(screen.getByTestId('delhi-fw-source-category').textContent).toMatch(/Typed by staff, not in Needle’s list/);
        expect(document.querySelectorAll('#delhi-fw-categories option').length).toBe(0);
    });

    it('a partial catalogue is labelled partial, keeps portal order and raw text, and never blocks a typed category', async () => {
        await renderWs();
        type(/Department \*/, 'Partial Department');
        await waitFor(() => expect(screen.getByTestId('delhi-fw-dept-status').getAttribute('data-tone')).toBe('partial'));
        const status = screen.getByTestId('delhi-fw-dept-status').textContent;
        expect(status).toMatch(/Partial list/);
        expect(status).toMatch(/not proof of what the filing form shows/);
        expect(status).toMatch(/Filing is not blocked/);
        const cats = [...document.querySelectorAll('#delhi-fw-categories option')].map((o) => o.value);
        expect(cats).toEqual(['Zeta first', 'Alpha &amp;amp; second']);          // portal order (not alphabetical); entity text not decoded
        expect(screen.getByLabelText(/Grievance Category \*/).value).toBe('');   // nothing is auto-selected
        type(/Grievance Category \*/, 'Alpha &amp;amp; second');
        expect(screen.getByTestId('delhi-fw-row-unverified').textContent).toMatch(/not been text-verified/);
        type(/Grievance Category \*/, 'Something typed from the portal');
        expect(screen.getByTestId('delhi-fw-source-category').textContent).toMatch(/Typed by staff, not in Needle’s list/);
        expect(screen.queryByTestId('delhi-fw-row-unverified')).toBeNull();
    });

    it('a complete catalogue says it is not proof that every category appears in the filing form', async () => {
        await renderWs();
        type(/Department \*/, 'Delhi Police');
        await waitFor(() => expect(screen.getByTestId('delhi-fw-dept-status').getAttribute('data-tone')).toBe('ok'));
        expect(screen.getByTestId('delhi-fw-dept-status').textContent).toMatch(/not proof that every category appears in the form/);
    });

    it('a category that is not in the list of a COMPLETE department shows a warning, is saved as typed/unverified and can still be Ready', async () => {
        const post = vi.fn().mockResolvedValue(okSave({
            saved: { selection_sources: { department: 'staff_confirmed', category: 'staff_typed_unverified', location: 'staff_typed_unverified' } },
            validation: { ok: true, ready_to_file: true, errors: [], warnings: [{ field: 'category', code: 'not_in_catalogue_unverified', message: 'Not in Needle’s copy of the mapping list; not blocked.' }], notices: [] },
        }));
        await renderWs({ post });
        type(/Department \*/, 'Delhi Police');                     // complete in this fixture
        await waitFor(() => expect(screen.getByTestId('delhi-fw-dept-status').getAttribute('data-tone')).toBe('ok'));
        expect(screen.queryByTestId('delhi-fw-category-unlisted-warning')).toBeNull();          // nothing typed yet
        type(/Grievance Category \*/, 'A category only on the filing form');
        expect(screen.getByTestId('delhi-fw-category-unlisted-warning').textContent).toMatch(/not in Needle’s copy.*not blocked|filing is not blocked/i);
        expect(screen.getByLabelText(/Grievance Category \*/).value).toBe('A category only on the filing form');   // never substituted
        expect(screen.getByTestId('delhi-fw-source-category').textContent).toMatch(/Typed by staff, not in Needle’s list/);
        expect(screen.queryByTestId('delhi-fw-escalation')).toBeNull();
        type(/Location \*/, 'Typed Location');
        type(/Grievance Details/, 'Synthetic details');
        type(/Grievance Area Address/, 'Synthetic area');
        type(/^Name \*/, 'Synthetic Name');
        type(/Father\/Husband Name/, 'Synthetic Father');
        type(/Gender/, 'Female');
        type(/Residential Address/, 'Synthetic home');
        fireEvent.click(screen.getByRole('button', { name: 'Save filing worksheet' }));
        await screen.findByTestId('delhi-fw-ready');
        const [, body] = post.mock.calls[0];
        expect(body.category).toBe('A category only on the filing form');
        expect(body.selection_sources.category).toBe('staff_typed_unverified');
        expect(screen.getByTestId('delhi-fw-ready').textContent).toMatch(/the portal has not seen this complaint/);
        expect(screen.getByText(/Not in Needle’s copy of the mapping list; not blocked\./)).toBeTruthy();   // server warning displayed
    });

    it('an AI-suggested category that is not in the list stays unconfirmed until staff click, and then is typed/unverified', async () => {
        const post = vi.fn().mockResolvedValue({ success: true, suggestion: { department: 'Delhi Police', category: 'Not listed anywhere', source: 'ai_suggested' } });
        await renderWs({ post });
        type(/Department \*/, 'Delhi Police');
        await waitFor(() => expect(screen.getByTestId('delhi-fw-dept-status').textContent).toMatch(/holds 3/));
        fireEvent.click(screen.getByRole('button', { name: /Suggest department with AI/ }));
        const box = await screen.findByTestId('delhi-fw-suggestion');
        expect(screen.getByLabelText(/Grievance Category \*/).value).toBe('');                 // not selected silently
        fireEvent.click(within(box).getByRole('button', { name: 'Select this category' }));
        expect(screen.getByLabelText(/Grievance Category \*/).value).toBe('Not listed anywhere');
        expect(screen.getByTestId('delhi-fw-source-category').textContent).toMatch(/Typed by staff, not in Needle’s list/);
        expect(screen.getByTestId('delhi-fw-category-unlisted-warning')).toBeTruthy();
    });

    it('choosing a department never fills in a category', async () => {
        await renderWs();
        type(/Department \*/, 'Delhi Police');
        await waitFor(() => expect(screen.getByTestId('delhi-fw-dept-status').textContent).toMatch(/holds 3/));
        expect(screen.getByLabelText(/Grievance Category \*/).value).toBe('');
        expect(screen.queryByTestId('delhi-fw-escalation')).toBeNull();
    });

    it('a department name that is not one of the portal’s is flagged', async () => {
        await renderWs();
        type(/Department \*/, 'Imaginary Department');
        expect(screen.getByTestId('delhi-fw-dept-status').textContent).toMatch(/not one of the 90 department names/);
        expect(screen.getByTestId('delhi-fw-source-department').textContent).toMatch(/Typed by staff/);
    });

    it('shows the verified 250-character counters and the unknown-maximum counter for Grievance Details', async () => {
        await renderWs();
        type(/Residential Address/, 'a'.repeat(260));
        expect(screen.getByTestId('delhi-fw-residential-count').textContent).toBe('260 / 250 characters');
        type(/Grievance Area Address/, 'b'.repeat(10));
        expect(screen.getByTestId('delhi-fw-area-count').textContent).toBe('10 / 250 characters');
        type(/Grievance Details/, 'c'.repeat(3000));
        expect(screen.getByTestId('delhi-fw-details-count').textContent).toBe('3000 characters (the portal\'s maximum is not known)');
        expect(screen.getByTestId('delhi-fw-special-note').textContent).toMatch(/no character is rejected/);
    });

    it('Group Grievance hides Father/Husband Name and Gender and renames the name field', async () => {
        await renderWs();
        expect(screen.getByLabelText(/Father\/Husband Name/)).toBeTruthy();
        fireEvent.click(screen.getByLabelText(/Group Grievance/));
        expect(screen.queryByLabelText(/Father\/Husband Name/)).toBeNull();
        expect(screen.queryByLabelText(/Gender/)).toBeNull();
        expect(screen.getByLabelText(/Group \/ organisation name/)).toBeTruthy();
    });

    it('AI suggestion is displayed separately and only becomes a selection when staff click it', async () => {
        const post = vi.fn().mockResolvedValue({ success: true, suggestion: { department: 'Delhi Police', category: 'Corruption', source: 'ai_suggested' } });
        await renderWs({ post });
        fireEvent.click(screen.getByRole('button', { name: /Suggest department with AI/ }));
        const box = await screen.findByTestId('delhi-fw-suggestion');
        expect(box.textContent).toMatch(/AI suggestion \(not selected\)/);
        expect(screen.getByLabelText(/Department \*/).value).toBe('');            // nothing pre-filled
        expect(post).toHaveBeenCalledWith('/api/cases/7/govt/delhi/suggest', {});
        fireEvent.click(within(box).getByRole('button', { name: 'Select this department' }));
        expect(screen.getByLabelText(/Department \*/).value).toBe('Delhi Police');
        expect(screen.getByTestId('delhi-fw-source-department').textContent).toMatch(/Chosen from Needle’s copy/);
    });

    it('a failed AI suggestion shows an error and leaves the form alone', async () => {
        const post = vi.fn().mockRejectedValue(httpError(502, 'x'));
        await renderWs({ post });
        fireEvent.click(screen.getByRole('button', { name: /Suggest department with AI/ }));
        expect((await screen.findByRole('alert')).textContent).toMatch(/choose the department yourself/i);
        expect(screen.queryByTestId('delhi-fw-suggestion')).toBeNull();
    });

    it('saves the worksheet with provenance and attachment METADATA only, then shows "ready" without claiming it was filed', async () => {
        const post = vi.fn().mockResolvedValue(okSave());
        const onSaved = vi.fn();
        const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
        await renderWs({ post, onSaved });
        type(/Department \*/, 'Delhi Police');
        await waitFor(() => expect(screen.getByTestId('delhi-fw-dept-status').textContent).toMatch(/holds 3/));
        type(/Grievance Category \*/, 'Abuse of Power');
        type(/Location \*/, 'Typed Location');
        type(/Grievance Details/, 'Synthetic details');
        type(/Grievance Area Address/, 'Synthetic area');
        type(/^Name \*/, 'Synthetic Name');
        type(/Father\/Husband Name/, 'Synthetic Father');
        type(/Gender/, 'Female');
        type(/Residential Address/, 'Synthetic home');
        const file = new File([new Uint8Array(10)], 'proof_1.pdf', { type: 'application/pdf' });
        fireEvent.change(screen.getByLabelText(/Supporting document/), { target: { files: [file] } });
        fireEvent.click(screen.getByRole('button', { name: 'Save filing worksheet' }));
        await screen.findByTestId('delhi-fw-ready');

        const [url, body] = post.mock.calls[0];
        expect(url).toBe('/api/cases/7/govt/delhi/filing-worksheet');
        expect(body.selection_sources).toEqual({ department: 'staff_confirmed', category: 'staff_confirmed', location: 'staff_typed_unverified' });
        expect(body.attachment).toEqual({ filename: 'proof_1.pdf', size_bytes: 10, content_type: 'application/pdf' });
        expect(JSON.stringify(body)).not.toMatch(/mobile_1/);                   // never collected
        expect(screen.getByTestId('delhi-fw-ready').textContent).toMatch(/the portal has not seen this complaint/);
        expect(screen.getByRole('status').textContent).toMatch(/Nothing has been sent to the portal/);
        expect(screen.queryByText(/submitted|filed successfully|verified/i)).toBeNull();
        expect(onSaved).toHaveBeenCalledWith({ kind: 'worksheet_saved' });
        expect(openSpy).not.toHaveBeenCalled();                                // never opens/contacts the portal
        // copy-ready values in portal order
        expect(screen.getByTestId('delhi-fw-copy-Grievance Category').textContent).toBe('Abuse of Power');
        expect(screen.getByTestId('delhi-fw-copy-Location').textContent).toBe('Typed Location');
    });

    it('shows server-side errors, warnings and the special-character notice, and does not say ready', async () => {
        const post = vi.fn().mockResolvedValue(okSave({
            validation: {
                ok: false, ready_to_file: false,
                errors: [{ field: 'residential_address', code: 'too_long', message: 'Residential Address can have at most 250 characters (now 260).' }],
                warnings: [{ field: 'grievance_details', code: 'long_unknown_limit', message: 'Grievance Details is 5000 characters. The portal\'s maximum is not known.' }],
                notices: [{ field: 'grievance_details', code: 'special_characters_note', message: RULES.grievance_details.special_chars_notice }],
            },
        }));
        await renderWs({ post });
        fireEvent.click(screen.getByRole('button', { name: 'Save filing worksheet' }));
        await screen.findByTestId('delhi-fw-validation');
        expect(screen.getByTestId('delhi-fw-errors').textContent).toMatch(/at most 250/);
        expect(screen.getByTestId('delhi-fw-warnings').textContent).toMatch(/maximum is not known/);
        expect(screen.getByTestId('delhi-fw-notices').textContent).toMatch(/avoid special characters/);
        expect(screen.queryByTestId('delhi-fw-ready')).toBeNull();
        expect(screen.getByRole('status').textContent).toMatch(/saved as a draft/);
    });

    it('a bad PDF is flagged immediately, before saving', async () => {
        await renderWs();
        const file = new File([new Uint8Array(2 * 1024 * 1024)], 'my proof.pdf', { type: 'application/pdf' });
        fireEvent.change(screen.getByLabelText(/Supporting document/), { target: { files: [file] } });
        const errs = screen.getByTestId('delhi-fw-errors').textContent;
        expect(errs).toMatch(/1 MB/);
        expect(errs).toMatch(/spaces/);
    });

    it('a 409 (already filed by someone else) is reported and the parent is told to refresh', async () => {
        const post = vi.fn().mockRejectedValue(httpError(409, 'This case is already filed on the government portal (reference 2026).'));
        const onSaved = vi.fn();
        await renderWs({ post, onSaved });
        fireEvent.click(screen.getByRole('button', { name: 'Save filing worksheet' }));
        expect((await screen.findByRole('alert')).textContent).toMatch(/already filed/);
        expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ kind: 'conflict' }));
    });

    it('restores a previously saved worksheet and AI suggestion from the case', async () => {
        const govtCase = { govt_submission_worksheet: { subject: 's', description: 'd', delhi_filing: {
            department: 'Delhi Police', category: 'Corruption', location: 'Loc', grievance_details: 'saved text', group_grievance: false,
            selection_sources: { department: 'staff_confirmed' },
            ai_suggestions: { department: 'Delhi Police', category: null, source: 'ai_suggested' },
        } } };
        await renderWs({ govtCase });
        expect(screen.getByLabelText(/Department \*/).value).toBe('Delhi Police');
        expect(screen.getByLabelText(/Grievance Details/).value).toBe('saved text');
        expect(screen.getByTestId('delhi-fw-suggestion').textContent).toMatch(/AI suggestion \(not selected\)/);
    });

    it('offers the AI-drafted description only while Grievance Details is empty', async () => {
        await renderWs({ ai: 'AI drafted text' });
        fireEvent.click(screen.getByRole('button', { name: /Use the AI-drafted description/ }));
        expect(screen.getByLabelText(/Grievance Details/).value).toBe('AI drafted text');
        expect(screen.queryByRole('button', { name: /Use the AI-drafted description/ })).toBeNull();
    });

    it('if the catalogue cannot be loaded, staff can still type values and are told Needle cannot check them', async () => {
        await renderWs({ get: makeGet({ catalogueFails: true }) });
        expect(screen.getByTestId('delhi-fw-catalogue-error').textContent).toMatch(/cannot check them/);
        type(/Department \*/, 'Anything');
        expect(screen.getByLabelText(/Department \*/).value).toBe('Anything');
    });
});
