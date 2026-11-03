'use client';

import { useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { apiGet, apiPost } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

// Delhi CM Jan Sunwai FILING WORKSHEET (staff-assisted). Facts and rules: modules/govt_sync/delhi_filing.py and
// modules/data/delhi_catalogue.json, served by GET /api/govt/delhi/catalogue[/categories].
//
// What this does: lets staff pick the department / category / location from the portal's own text, enter the
// applicant and grievance fields in the order the portal asks for them, see the VERIFIED limits, and keep a copy-ready
// worksheet. What it never does: contact the portal, enter an OTP/CAPTCHA, upload the attachment, or mark anything
// as filed. "Ready" below means only "the verified portal rules are satisfied".
//
// Provenance (always shown): AI suggestion  /  chosen from Needle's list  /  typed by staff, not in Needle's list.
// The server re-derives provenance and re-validates; nothing here is trusted.

const C = {
    surface: '#FFFDF8', ink: '#24251F', ink2: '#62635B', ink3: '#6F7068', hair: '#D9D2C4',
    saffron: '#BC6A36', saffronTint: '#F5E7D8', green: '#234F3A', greenTint: '#E4ECE5', red: '#B3341C', redTint: '#F6E0D9',
};
const box = { background: C.surface, border: `1px solid ${C.hair}`, padding: '10px 12px', fontSize: '0.8125rem', color: C.ink2, lineHeight: 1.55 };
const heading = { fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: C.ink3, marginBottom: 4 };
const labelStyle = { display: 'block', fontSize: '0.75rem', fontWeight: 600, color: C.ink, marginBottom: 2 };
const noteStyle = { fontSize: '0.75rem', color: C.ink3, marginTop: 3 };
const areaStyle = { width: '100%', fontSize: '0.78125rem', padding: '8px 10px', border: `1px solid ${C.hair}`, background: '#fff', color: C.ink, fontFamily: 'inherit' };

export const SOURCE_LABEL = {
    ai_suggested: 'AI suggestion, not confirmed',
    staff_confirmed: 'Chosen from Needle’s copy of the portal list',
    staff_typed_unverified: 'Typed by staff, not in Needle’s list: copy it exactly as the portal shows it',
};

// ── API helpers (pure, injectable, tested) ─────────────────────────────────────────────────────────
function classify(e, fallback) {
    if (e?.status === 403) return { kind: 'disabled', message: 'Delhi staff-assisted filing is not enabled for this account yet.' };
    if (e?.status === 404) return { kind: 'not_found', message: 'This case could not be found. Refresh the page and try again.' };
    if (e?.status === 409) return { kind: 'conflict', message: e.message || 'This case already has a government record, so the worksheet can no longer be changed.' };
    if (e?.status === 400) return { kind: 'error', message: e.message || 'Delhi filing support is not available for this case.' };
    if (e?.status === 502) return { kind: 'error', message: 'The AI suggestion failed. Choose the department yourself or try again in a moment.' };
    return { kind: 'error', message: fallback };
}

export async function fetchDelhiCatalogue(get = apiGet) {
    try {
        const r = await get('/api/govt/delhi/catalogue');
        if (!r || !Array.isArray(r.departments) || !r.field_rules) return { kind: 'error', message: 'The Delhi department list could not be loaded.' };
        return { kind: 'loaded', departments: r.departments, rules: r.field_rules, meta: r.meta || {} };
    } catch (e) {
        return classify(e, 'The Delhi department list could not be loaded.');
    }
}

export async function fetchDelhiCategories(department, get = apiGet) {
    try {
        const r = await get(`/api/govt/delhi/catalogue/categories?department=${encodeURIComponent(department)}`);
        if (!r || !Array.isArray(r.categories)) return { kind: 'error', message: 'The category list could not be loaded.' };
        return { kind: 'loaded', info: r };
    } catch (e) {
        return classify(e, 'The category list could not be loaded.');
    }
}

export async function suggestDelhiDepartment(caseId, post = apiPost) {
    try {
        const r = await post(`/api/cases/${caseId}/govt/delhi/suggest`, {});
        if (!r || r.success !== true || !r.suggestion) return { kind: 'error', message: 'The AI suggestion could not be confirmed.' };
        return { kind: 'suggested', suggestion: r.suggestion };
    } catch (e) {
        return classify(e, 'The AI suggestion failed. Check your connection and try again.');
    }
}

export async function saveDelhiFilingWorksheet(caseId, payload, post = apiPost) {
    try {
        const r = await post(`/api/cases/${caseId}/govt/delhi/filing-worksheet`, payload);
        if (!r || r.success !== true || !r.validation) return { kind: 'error', message: 'The worksheet could not be confirmed as saved. Please try again.' };
        return { kind: 'saved', saved: r.saved, validation: r.validation };
    } catch (e) {
        return classify(e, 'Could not save the worksheet. Check your connection and try again.');
    }
}

// Pre-check of the optional supporting document using the SAME rules the backend serves. Nothing is uploaded.
export function checkDelhiAttachment(file, rules) {
    const a = rules?.attachment;
    if (!file || !a) return [];
    const out = [];
    const name = String(file.name || '');
    if (!name.toLowerCase().endsWith(a.extension) || (file.type && file.type !== a.content_type)) out.push('Only PDF files are accepted by the portal.');
    if (typeof file.size === 'number' && file.size > a.max_bytes) out.push('The portal accepts a PDF of at most 1 MB.');
    if (name.includes(' ')) out.push('The file name must not contain spaces.');
    if (name.includes('(') || name.includes(')')) out.push('The file name must not contain parentheses.');
    if (name.includes('..')) out.push('The file name must not contain “..”.');
    const bad = [...new Set([...name].filter((ch) => a.forbidden_name_chars.includes(ch)))];
    if (bad.length) out.push(`The file name contains characters the portal does not allow: ${bad.join(' ')}`);
    if (name.length > a.max_name_chars) out.push('The file name must be shorter than 100 characters.');
    return out;
}

const EMPTY = {
    group_grievance: false, applicant_name: '', father_husband_name: '', gender: '', residential_address: '', mobile_2: '', email: '',
    department: '', category: '', location: '', grievance_details: '', grievance_area_address: '', old_reference_number: '',
};

function Counter({ value, max, id }) {
    const n = (value || '').length;
    const over = max != null && n > max;
    return <div id={id} data-testid={id} style={{ ...noteStyle, color: over ? C.red : C.ink3 }}>{max != null ? `${n} / ${max} characters` : `${n} characters (the portal's maximum is not known)`}</div>;
}

function Issues({ list, tone }) {
    if (!list?.length) return null;
    const s = tone === 'error' ? { background: C.redTint, color: C.red, border: `1px solid ${C.red}` }
        : tone === 'warning' ? { background: C.saffronTint, color: C.ink2, border: `1px solid ${C.saffron}` }
            : { background: C.surface, color: C.ink2, border: `1px solid ${C.hair}` };
    return (
        <ul data-testid={`delhi-fw-${tone}s`} style={{ ...s, fontSize: '0.75rem', margin: '6px 0 0', padding: '8px 10px 8px 26px', listStyle: 'disc' }}>
            {list.map((i, idx) => <li key={`${i.field}-${i.code}-${idx}`}>{i.message}</li>)}
        </ul>
    );
}

function CopyRow({ label, value }) {
    const [copied, setCopied] = useState(false);
    if (!String(value || '').trim()) return null;
    return (
        <div style={{ marginBottom: 6 }}>
            <div style={{ ...heading, marginBottom: 1 }}>{label}</div>
            <div data-testid={`delhi-fw-copy-${label}`} style={{ ...box, whiteSpace: 'pre-wrap', color: C.ink, padding: '6px 10px' }}>{value}</div>
            <button type="button" onClick={async () => { try { await navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard unavailable */ } }}
                style={{ fontSize: '0.75rem', background: 'none', border: 'none', color: C.green, cursor: 'pointer', padding: 0 }}>
                {copied ? 'Copied' : `Copy ${label}`}
            </button>
        </div>
    );
}

export default function DelhiFilingWorksheet({ caseId, govtCase, aiDraftDescription = '', onSaved, getFn = apiGet, postFn = apiPost }) {
    const stored = useMemo(() => {
        let ws = govtCase?.govt_submission_worksheet;
        if (typeof ws === 'string') { try { ws = JSON.parse(ws); } catch { ws = null; } }
        return ws && typeof ws === 'object' ? ws : null;
    }, [govtCase]);
    const saved = stored?.delhi_filing || null;

    const [catalogue, setCatalogue] = useState({ kind: 'loading' });
    const [form, setForm] = useState(() => ({ ...EMPTY, ...Object.fromEntries(Object.keys(EMPTY).map((k) => [k, saved?.[k] ?? EMPTY[k]])) }));
    const [sources, setSources] = useState(saved?.selection_sources || {});
    const [deptInfo, setDeptInfo] = useState(null);
    const [deptLoading, setDeptLoading] = useState(false);
    const [suggestion, setSuggestion] = useState(saved?.ai_suggestions || null);
    const [suggestBusy, setSuggestBusy] = useState(false);
    const [saveBusy, setSaveBusy] = useState(false);
    const [attachment, setAttachment] = useState(saved?.attachment || null);
    const [attachErrors, setAttachErrors] = useState([]);
    const [result, setResult] = useState(null);          // { validation } from the last save
    const [message, setMessage] = useState(null);

    useEffect(() => {
        let live = true;
        fetchDelhiCatalogue(getFn).then((c) => { if (live) setCatalogue(c); });
        return () => { live = false; };
    }, [getFn]);

    const deptNames = useMemo(() => (catalogue.kind === 'loaded' ? catalogue.departments.map((d) => d.name) : []), [catalogue]);
    const rules = catalogue.kind === 'loaded' ? catalogue.rules : null;
    const deptIsCatalogued = !!form.department && deptNames.includes(form.department.trim());

    useEffect(() => {
        let live = true;
        const dept = form.department.trim();
        if (!dept || !deptNames.includes(dept)) { setDeptInfo(null); return undefined; }
        setDeptLoading(true);
        fetchDelhiCategories(dept, getFn).then((r) => { if (live) { setDeptInfo(r.kind === 'loaded' ? r.info : null); setDeptLoading(false); } });
        return () => { live = false; };
    }, [form.department, deptNames, getFn]);

    const categories = deptInfo?.categories || [];
    const chosenCategory = categories.find((c) => c.text === form.category.trim()) || null;
    const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

    // Provenance as the CLIENT understands it; the server recomputes it and is the source of truth.
    const sourceFor = (k) => {
        const v = String(form[k] || '').trim();
        if (!v) return null;
        if (sources[k] === 'ai_suggested') return 'ai_suggested';
        if (k === 'department') return deptNames.includes(v) ? 'staff_confirmed' : 'staff_typed_unverified';
        if (k === 'category') return categories.some((c) => c.text === v) ? 'staff_confirmed' : 'staff_typed_unverified';
        return 'staff_typed_unverified';
    };

    async function handleSuggest() {
        if (suggestBusy) return;
        setSuggestBusy(true); setMessage(null);
        const out = await suggestDelhiDepartment(caseId, postFn);
        setSuggestBusy(false);
        if (out.kind === 'suggested') { setSuggestion(out.suggestion); await onSaved?.({ kind: 'suggested' }); }
        else setMessage({ tone: 'error', text: out.message });
    }
    // Clicking is the staff confirmation: the value becomes staff_confirmed, the suggestion stays visible as AI output.
    function acceptSuggestedDepartment() { setSources((s) => ({ ...s, department: 'staff_confirmed' })); set('department', suggestion.department); }
    function acceptSuggestedCategory() { setSources((s) => ({ ...s, category: 'staff_confirmed' })); set('category', suggestion.category); }

    function handleFile(e) {
        const f = e.target.files?.[0];
        if (!f) { setAttachment(null); setAttachErrors([]); return; }
        setAttachErrors(checkDelhiAttachment(f, rules));
        setAttachment({ filename: f.name, size_bytes: f.size, content_type: f.type || 'application/pdf' });
    }

    async function handleSave() {
        if (saveBusy) return;
        setSaveBusy(true); setMessage(null);
        const payload = { ...form, attachment, selection_sources: Object.fromEntries(['department', 'category', 'location'].map((k) => [k, sourceFor(k)]).filter(([, v]) => v)) };
        const out = await saveDelhiFilingWorksheet(caseId, payload, postFn);
        setSaveBusy(false);
        if (out.kind === 'saved') {
            setResult(out.validation);
            setSources(out.saved?.selection_sources || {});
            setMessage({ tone: out.validation.ready_to_file ? 'ok' : 'info', text: out.validation.ready_to_file
                ? 'Worksheet saved. The portal rules Needle knows are satisfied. Nothing has been sent to the portal.'
                : 'Worksheet saved as a draft. Fix the items below before filing. Nothing has been sent to the portal.' });
            await onSaved?.({ kind: 'worksheet_saved' });
        } else {
            if (out.kind === 'conflict' || out.kind === 'not_found') await onSaved?.(out);
            setMessage({ tone: 'error', text: out.message });
        }
    }

    const toneStyle = (tone) => (tone === 'error' ? { background: C.redTint, color: C.red, border: `1px solid ${C.red}` }
        : tone === 'ok' ? { background: C.greenTint, color: C.green, border: `1px solid ${C.green}` }
            : { background: C.saffronTint, color: C.ink2, border: `1px solid ${C.saffron}` });

    const deptStatusLine = (() => {
        if (!form.department.trim()) return null;
        if (!deptIsCatalogued) return { tone: 'error', text: 'This is not one of the 90 department names on the portal. Pick one from the list.' };
        if (deptLoading) return { tone: 'info', text: 'Loading this department’s categories…' };
        if (deptInfo?.categories_complete) return { tone: 'ok', text: `Needle holds ${categories.length} categories for this department, in the portal’s order (captured from the portal’s public mapping page; ${deptInfo.form_comparison === 'pending' ? 'not yet compared with the filing form’s own dropdown, so this list is not proof that every category appears in the form' : 'compared with the filing form'}). If the filing form shows a category that is not listed, check it on the portal.` };
        if (categories.length > 0) return { tone: 'partial', text: `Partial list: Needle holds ${categories.length} categories for this department, but ${deptInfo.unverified_row_count || 'some'} of them have long text that has not been fully verified, and the list is not proof of what the filing form shows. Check the category on the portal before relying on it. You can still type a category exactly as the portal shows it. Filing is not blocked.` };
        return { tone: 'info', text: 'Needle has not captured this department’s category list. Choose the category on the portal and type it here exactly as the portal shows it. Filing is not blocked.' };
    })();

    const badge = (k) => {
        const s = sourceFor(k);
        return s ? <div data-testid={`delhi-fw-source-${k}`} style={{ ...noteStyle, color: s === 'staff_confirmed' ? C.green : C.saffron }}>{SOURCE_LABEL[s]}</div> : null;
    };

    return (
        <div data-testid="delhi-filing-worksheet" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={heading}>1b · Filing worksheet: department, category, location and applicant</div>
            <div style={box}>
                Fill this in, then type the same values on the official portal after you have completed its OTP and CAPTCHA yourself.
                <strong style={{ color: C.ink }}> Needle does not fill in or submit the portal form.</strong> Mobile No. 1 is pre-filled by the portal from your OTP, so Needle does not collect it.
            </div>

            {catalogue.kind === 'loading' && <div role="status" style={noteStyle}>Loading the Delhi department list…</div>}
            {(catalogue.kind === 'error' || catalogue.kind === 'disabled' || catalogue.kind === 'not_found') && (
                <div role="status" data-testid="delhi-fw-catalogue-error" style={{ ...box, ...toneStyle('error') }}>
                    {catalogue.message} You can still type the department and category exactly as the portal shows them; Needle just cannot check them.
                </div>
            )}

            {/* AI suggestion: separate from selections */}
            <div data-testid="delhi-fw-ai">
                <Button type="button" size="sm" variant="outline" disabled={suggestBusy} onClick={handleSuggest}>
                    {suggestBusy ? <Loader2 size={14} className="animate-spin" /> : 'Suggest department with AI'}
                </Button>
                {suggestion && (
                    <div data-testid="delhi-fw-suggestion" style={{ ...box, marginTop: 6 }}>
                        <strong style={{ color: C.ink }}>AI suggestion (not selected):</strong>{' '}
                        {suggestion.department ? <>department “{suggestion.department}”</> : 'no department clearly fits'}
                        {suggestion.category ? <>, category “{suggestion.category}”</> : null}.
                        <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
                            {suggestion.department && <Button type="button" size="sm" variant="outline" onClick={acceptSuggestedDepartment}>Select this department</Button>}
                            {suggestion.department && suggestion.category && <Button type="button" size="sm" variant="outline" onClick={acceptSuggestedCategory}>Select this category</Button>}
                        </div>
                        <div style={noteStyle}>You decide: review the department and category before selecting.</div>
                    </div>
                )}
            </div>

            {/* Grievance selections */}
            <div>
                <label htmlFor="delhi-fw-department" style={labelStyle}>Department *</label>
                <Input id="delhi-fw-department" list="delhi-fw-departments" value={form.department} onChange={(e) => { setSources((s) => ({ ...s, department: undefined })); set('department', e.target.value); }} placeholder="Start typing the department name" style={{ fontSize: '0.78125rem' }} />
                <datalist id="delhi-fw-departments">{deptNames.map((n) => <option key={n} value={n} />)}</datalist>
                {badge('department')}
                {deptStatusLine && <div data-testid="delhi-fw-dept-status" data-tone={deptStatusLine.tone} style={{ ...noteStyle, color: deptStatusLine.tone === 'error' ? C.red : deptStatusLine.tone === 'partial' ? C.saffron : C.ink3 }}>{deptStatusLine.text}</div>}
            </div>

            <div>
                <label htmlFor="delhi-fw-category" style={labelStyle}>Grievance Category *</label>
                <Input id="delhi-fw-category" list="delhi-fw-categories" value={form.category} onChange={(e) => { setSources((s) => ({ ...s, category: undefined })); set('category', e.target.value); }} placeholder={categories.length ? 'Start typing, then pick the category exactly as listed' : 'Type exactly as the portal shows it'} style={{ fontSize: '0.78125rem' }} />
                <datalist id="delhi-fw-categories">{categories.map((c) => <option key={c.seq} value={c.text} />)}</datalist>
                {badge('category')}
                {categories.length > 0 && form.category.trim() && !chosenCategory && (
                    <div role="note" data-testid="delhi-fw-category-unlisted-warning" style={{ ...noteStyle, color: C.saffron }}>
                        This category is not in Needle’s copy of the portal’s mapping list for this department. That list has not been compared with the filing form, so filing is not blocked. Check it on the portal and type it exactly as shown. It will be recorded as typed by staff and unverified.
                    </div>
                )}
                {chosenCategory && (
                    <div data-testid="delhi-fw-escalation" style={{ ...box, marginTop: 6, fontSize: '0.75rem' }}>
                        <div>Escalation chain the portal lists for this category (days fixed for disposal):</div>
                        {['l1', 'l2', 'l3'].map((l) => <div key={l}>{l.toUpperCase()}: {chosenCategory[l].post} · {chosenCategory[l].disposal_days} days</div>)}
                        {chosenCategory.verification === 'screenshot_repaired_not_text_verified' && (
                            <div data-testid="delhi-fw-row-unverified" style={{ ...noteStyle, color: C.saffron }}>This row’s long text was recovered from a screenshot and has not been text-verified. Check it on the portal.</div>
                        )}
                    </div>
                )}
            </div>

            <div>
                <label htmlFor="delhi-fw-location" style={labelStyle}>Location *</label>
                <Input id="delhi-fw-location" value={form.location} onChange={(e) => { setSources((s) => ({ ...s, location: undefined })); set('location', e.target.value); }} placeholder="As shown in the portal’s Location list" style={{ fontSize: '0.78125rem' }} />
                {badge('location')}
                <div style={noteStyle}>The portal’s location list depends on the department and category. Needle has not captured these lists, so choose it on the portal and type it exactly as shown.</div>
            </div>

            {/* Grievance text */}
            <div>
                <label htmlFor="delhi-fw-details" style={labelStyle}>Grievance Details *</label>
                <textarea id="delhi-fw-details" rows={5} value={form.grievance_details} onChange={(e) => set('grievance_details', e.target.value)} style={areaStyle} />
                <Counter id="delhi-fw-details-count" value={form.grievance_details} max={null} />
                <div data-testid="delhi-fw-special-note" style={noteStyle}>{rules?.grievance_details?.special_chars_notice || 'The portal advises avoiding special characters in Grievance Details.'}</div>
                {aiDraftDescription && !form.grievance_details.trim() && (
                    <button type="button" onClick={() => set('grievance_details', aiDraftDescription)} style={{ fontSize: '0.75rem', background: 'none', border: 'none', color: C.green, cursor: 'pointer', padding: 0, marginTop: 4 }}>
                        Use the AI-drafted description
                    </button>
                )}
            </div>
            <div>
                <label htmlFor="delhi-fw-area" style={labelStyle}>Grievance Area Address *</label>
                <textarea id="delhi-fw-area" rows={2} value={form.grievance_area_address} onChange={(e) => set('grievance_area_address', e.target.value)} style={areaStyle} />
                <Counter id="delhi-fw-area-count" value={form.grievance_area_address} max={rules?.address_max_chars ?? 250} />
            </div>

            {/* Applicant */}
            <div>
                <label style={{ ...labelStyle, display: 'flex', gap: 6, alignItems: 'center' }}>
                    <input type="checkbox" checked={form.group_grievance} onChange={(e) => set('group_grievance', e.target.checked)} /> Group Grievance
                </label>
                <div style={noteStyle}>With this ticked the portal changes the name field to the group’s name and disables Father/Husband Name and Gender.</div>
            </div>
            <div>
                <label htmlFor="delhi-fw-name" style={labelStyle}>{form.group_grievance ? 'Group / organisation name *' : 'Name *'}</label>
                <Input id="delhi-fw-name" value={form.applicant_name} onChange={(e) => set('applicant_name', e.target.value)} style={{ fontSize: '0.78125rem' }} />
            </div>
            {!form.group_grievance && (
                <>
                    <div>
                        <label htmlFor="delhi-fw-father" style={labelStyle}>Father/Husband Name *</label>
                        <Input id="delhi-fw-father" value={form.father_husband_name} onChange={(e) => set('father_husband_name', e.target.value)} style={{ fontSize: '0.78125rem' }} />
                    </div>
                    <div>
                        <label htmlFor="delhi-fw-gender" style={labelStyle}>Gender *</label>
                        <Input id="delhi-fw-gender" value={form.gender} onChange={(e) => set('gender', e.target.value)} placeholder="As in the portal’s Gender list" style={{ fontSize: '0.78125rem' }} />
                    </div>
                </>
            )}
            <div>
                <label htmlFor="delhi-fw-residential" style={labelStyle}>Residential Address *</label>
                <textarea id="delhi-fw-residential" rows={2} value={form.residential_address} onChange={(e) => set('residential_address', e.target.value)} style={areaStyle} />
                <Counter id="delhi-fw-residential-count" value={form.residential_address} max={rules?.address_max_chars ?? 250} />
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <div style={{ flex: '1 1 160px' }}>
                    <label htmlFor="delhi-fw-mobile2" style={labelStyle}>Mobile No. 2 (optional)</label>
                    <Input id="delhi-fw-mobile2" inputMode="numeric" value={form.mobile_2} onChange={(e) => set('mobile_2', e.target.value)} style={{ fontSize: '0.78125rem' }} />
                </div>
                <div style={{ flex: '1 1 200px' }}>
                    <label htmlFor="delhi-fw-email" style={labelStyle}>Email (optional)</label>
                    <Input id="delhi-fw-email" value={form.email} onChange={(e) => set('email', e.target.value)} style={{ fontSize: '0.78125rem' }} />
                </div>
                <div style={{ flex: '1 1 200px' }}>
                    <label htmlFor="delhi-fw-oldref" style={labelStyle}>Old reference number (optional)</label>
                    <Input id="delhi-fw-oldref" value={form.old_reference_number} onChange={(e) => set('old_reference_number', e.target.value)} style={{ fontSize: '0.78125rem' }} />
                </div>
            </div>

            {/* Optional PDF: checked here, attached by staff on the portal */}
            <div>
                <label htmlFor="delhi-fw-file" style={labelStyle}>Supporting document (optional)</label>
                <input id="delhi-fw-file" type="file" accept="application/pdf,.pdf" onChange={handleFile} />
                <div style={noteStyle}>PDF only, at most 1 MB, file name without spaces, brackets or special characters and shorter than 100 characters. Needle only checks the file here; you attach it on the portal. The file is not uploaded to Needle.</div>
                <Issues list={attachErrors.map((m, i) => ({ field: 'supporting_document', code: `a${i}`, message: m }))} tone="error" />
            </div>

            <div>
                <Button type="button" size="sm" disabled={saveBusy} onClick={handleSave}>
                    {saveBusy ? <Loader2 size={14} className="animate-spin" /> : 'Save filing worksheet'}
                </Button>
            </div>

            {message && <div role={message.tone === 'error' ? 'alert' : 'status'} style={{ fontSize: '0.75rem', padding: '8px 10px', ...toneStyle(message.tone) }}>{message.text}</div>}
            {result && (
                <div data-testid="delhi-fw-validation">
                    <Issues list={result.errors} tone="error" />
                    <Issues list={result.warnings} tone="warning" />
                    <Issues list={result.notices} tone="notice" />
                    {result.ready_to_file && (
                        <div data-testid="delhi-fw-ready" style={{ ...box, marginTop: 6 }}>
                            Ready to file on the official portal. This means only that the portal rules Needle knows are satisfied; the portal has not seen this complaint.
                        </div>
                    )}
                </div>
            )}

            {result && (
                <div data-testid="delhi-fw-copy">
                    <div style={heading}>Copy for the portal</div>
                    <CopyRow label="Department" value={form.department} />
                    <CopyRow label="Grievance Category" value={form.category} />
                    <CopyRow label="Location" value={form.location} />
                    <CopyRow label="Name" value={form.applicant_name} />
                    {!form.group_grievance && <CopyRow label="Father/Husband Name" value={form.father_husband_name} />}
                    {!form.group_grievance && <CopyRow label="Gender" value={form.gender} />}
                    <CopyRow label="Residential Address" value={form.residential_address} />
                    <CopyRow label="Grievance Details" value={form.grievance_details} />
                    <CopyRow label="Grievance Area Address" value={form.grievance_area_address} />
                    <CopyRow label="Old reference number" value={form.old_reference_number} />
                </div>
            )}
        </div>
    );
}
