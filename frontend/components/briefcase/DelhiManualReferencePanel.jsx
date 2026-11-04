'use client';

import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { apiPost } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import DelhiFilingWorksheet from './DelhiFilingWorksheet';

// Delhi CM Jan Sunwai: STAFF-ASSISTED workflow. Verified facts: DELHI_CM_JAN_SUNWAI_CAPABILITY_MAP.md.
//
// Every citizen operation on that portal (registration, status, reminder, feedback) needs a human to solve
// an image CAPTCHA and an SMS/e-mail OTP, and the department list plus the post-OTP pages are not public.
// So Needle: (1) drafts subject + description with AI (never a department), (2) opens the official page and
// lists exactly what the portal will ask for, (3) records the complaint number staff obtain (numeric, <= 14
// digits - the portal's own rule), (4) offers the status / reminder / feedback pages as audited staff tasks.
// Needle never contacts the portal, never reads a Delhi status and never claims it did. The portal is resolved
// server-side from the tenant; only a reference number (and a task key) is ever sent.

export const DELHI_PORTAL_NAME = 'Delhi CM Jan Sunwai';
export const DELHI_PORTAL_URL = 'https://cmjansunwai.delhi.gov.in/';
export const DELHI_REFERENCE_RE = /^[0-9]{1,14}$/;
export const DELHI_REFERENCE_RULE = 'The Delhi complaint number is numeric, up to 14 digits.';

// /api/govt-portal reports the tenant's state even while Delhi's own portal row is inactive, so state is the
// reliable signal here - never the resolved portal's id or name.
export function isDelhiPortalState(state) {
    return String(state || '').trim().toLowerCase() === 'delhi';
}

// True only for a case that is linked to the Delhi portal. The portal's state (a stable key joined onto the case by
// the backend) is preferred; the display name is only a fallback for rows that carry no state.
// Unknown or missing => false, so every other portal keeps the original, unchanged presentation.
export function isDelhiGovtCase(c) {
    const state = c?.govt_portal_state ?? c?.portal_state;
    if (state != null && String(state).trim() !== '') return isDelhiPortalState(state);
    return String(c?.govt_portal_name || c?.portal_name || '').trim() === DELHI_PORTAL_NAME;
}

export function openDelhiPortal() {
    window.open(DELHI_PORTAL_URL, '_blank', 'noopener,noreferrer');
}

function classifyError(e, fallback) {
    if (e?.status === 403) return { kind: 'disabled', message: 'Delhi staff-assisted filing is not enabled for this account yet. Please contact your administrator.' };
    if (e?.status === 404) return { kind: 'not_found', message: 'This case could not be found. Refresh the page and try again.' };
    if (e?.status === 409) return { kind: 'conflict', message: e.message || 'This case already has a different government record.' };
    if (e?.status === 400) return { kind: 'error', message: e.message || 'Delhi staff-assisted filing is not available for this case.' };
    if (e?.status === 502) return { kind: 'error', message: 'AI drafting failed. Please try again in a moment.' };
    return { kind: 'error', message: fallback };
}

// Pure outcome mapping, kept separate from the UI so every branch is testable.
export async function recordDelhiManualReference(caseId, referenceNumber, post = apiPost) {
    const reference = String(referenceNumber || '').trim();
    if (!reference) return { kind: 'invalid', message: 'Enter the complaint number the Delhi portal gave you.' };
    if (!DELHI_REFERENCE_RE.test(reference)) return { kind: 'invalid', message: `${DELHI_REFERENCE_RULE} Check the number shown by the portal.` };
    try {
        const result = await post(`/api/cases/${caseId}/govt/manual-reference`, { reference_number: reference });
        // Success is only what the backend confirms it saved.
        if (!result || result.success !== true || !String(result.govt_reference_number || '').trim()) {
            return { kind: 'error', message: 'The complaint number could not be confirmed as saved. Please check the case and try again.' };
        }
        return { kind: result.idempotent ? 'idempotent' : 'saved', reference: result.govt_reference_number, status: result.status };
    } catch (e) {
        return classifyError(e, 'Could not save the complaint number. Check your connection and try again.');
    }
}

export async function prepareDelhiWorksheet(caseId, post = apiPost) {
    try {
        const result = await post(`/api/cases/${caseId}/govt/delhi/prepare-worksheet`, {});
        const ws = result?.worksheet;
        if (!result || result.success !== true || !ws || !String(ws.subject || '').trim() || !String(ws.description || '').trim()) {
            return { kind: 'error', message: 'The AI draft could not be confirmed. Please try again.' };
        }
        return { kind: 'prepared', worksheet: ws, contactNumber: result.portal_contact_number || null };
    } catch (e) {
        return classifyError(e, 'Could not prepare the worksheet. Check your connection and try again.');
    }
}

export async function logDelhiTask(caseId, taskKey, post = apiPost) {
    try {
        const result = await post(`/api/cases/${caseId}/govt/delhi/task`, { task: taskKey });
        if (!result || result.success !== true) return { kind: 'error', message: 'The task could not be recorded.' };
        return { kind: 'logged', task: result.task };
    } catch (e) {
        return classifyError(e, 'Could not record this task. Check your connection.');
    }
}

const C = {
    surface: '#FFFDF8', paper: '#F4F0E7', ink: '#24251F', ink2: '#62635B', ink3: '#6F7068',
    hair: '#D9D2C4', saffron: '#BC6A36', saffronTint: '#F5E7D8', green: '#234F3A', greenTint: '#E4ECE5',
    red: '#B3341C', redTint: '#F6E0D9',
};
const box = { background: C.surface, border: `1px solid ${C.hair}`, padding: '10px 12px', fontSize: '0.8125rem', color: C.ink2, lineHeight: 1.55 };
const heading = { fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: C.ink3, marginBottom: 6 };

function CopyField({ label, value }) {
    const [copied, setCopied] = useState(false);
    return (
        <div style={{ marginBottom: 8 }}>
            <div style={{ ...heading, marginBottom: 2 }}>{label}</div>
            <div data-testid={`delhi-ws-${label.toLowerCase()}`} style={{ ...box, whiteSpace: 'pre-wrap', color: C.ink }}>{value}</div>
            <button type="button" onClick={async () => { try { await navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard unavailable */ } }}
                style={{ marginTop: 4, fontSize: '0.75rem', background: 'none', border: 'none', color: C.green, cursor: 'pointer', padding: 0 }}>
                {copied ? 'Copied' : `Copy ${label.toLowerCase()}`}
            </button>
        </div>
    );
}

export default function DelhiManualReferencePanel({
    caseId, govtCase, onRecorded, manualReferenceEnabled = false, tasks = null, portalContactNumber = null,
}) {
    const initialWs = govtCase?.govt_submission_worksheet;
    const [worksheet, setWorksheet] = useState(initialWs && initialWs.subject ? initialWs : null);
    const [contactNumber, setContactNumber] = useState(portalContactNumber);
    const [refInput, setRefInput] = useState('');
    const [busy, setBusy] = useState(false);
    const [prepBusy, setPrepBusy] = useState(false);
    const [message, setMessage] = useState(null); // { tone: 'ok' | 'info' | 'error', text }

    const storedRef = String(govtCase?.govt_reference_number || '').trim();
    const filed = !!storedRef;
    const taskList = Array.isArray(tasks) ? tasks : [];
    const taskByKey = (k) => taskList.find((t) => t.key === k);

    async function handlePrepare() {
        if (prepBusy) return;
        setPrepBusy(true);
        setMessage(null);
        const outcome = await prepareDelhiWorksheet(caseId);
        try {
            if (outcome.kind === 'prepared') {
                setWorksheet(outcome.worksheet);
                if (outcome.contactNumber) setContactNumber(outcome.contactNumber);
                await onRecorded?.({ kind: 'prepared' });
                setMessage({ tone: 'ok', text: 'Worksheet drafted. Review it, then file on the official portal. Nothing has been sent to the portal.' });
            } else {
                if (outcome.kind === 'conflict' || outcome.kind === 'not_found') await onRecorded?.(outcome);
                setMessage({ tone: 'error', text: outcome.message });
            }
        } finally {
            setPrepBusy(false);
        }
    }

    async function handleSave() {
        if (busy) return;
        setBusy(true);
        setMessage(null);
        const outcome = await recordDelhiManualReference(caseId, refInput);
        try {
            if (outcome.kind === 'saved') {
                setRefInput('');
                await onRecorded?.(outcome);
                setMessage({ tone: 'ok', text: `Complaint number ${outcome.reference} saved. This case is marked as submitted.` });
            } else if (outcome.kind === 'idempotent') {
                setRefInput('');
                await onRecorded?.(outcome);
                setMessage({ tone: 'info', text: `Complaint number ${outcome.reference} was already recorded for this case. Nothing changed.` });
            } else {
                if (outcome.kind === 'conflict' || outcome.kind === 'not_found') await onRecorded?.(outcome);
                setMessage({ tone: 'error', text: outcome.message });
            }
        } finally {
            setBusy(false);
        }
    }

    // window.open must run inside the click (popup blockers), so the page opens first and the audit entry follows.
    async function handleOpenTask(task) {
        window.open(task.url, '_blank', 'noopener,noreferrer');
        setMessage(null);
        const outcome = await logDelhiTask(caseId, task.key);
        if (outcome.kind !== 'logged') setMessage({ tone: 'error', text: outcome.message });
        else if (task.key !== 'file') await onRecorded?.({ kind: 'task_logged' });
    }

    const toneStyle = (tone) => (tone === 'error'
        ? { background: C.redTint, color: C.red, border: `1px solid ${C.red}` }
        : tone === 'ok'
            ? { background: C.greenTint, color: C.green, border: `1px solid ${C.green}` }
            : { background: C.saffronTint, color: C.ink2, border: `1px solid ${C.saffron}` });

    const fileTask = taskByKey('file');

    return (
        <div data-testid="delhi-manual-reference" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {!manualReferenceEnabled && !filed && (
                <div role="status" data-testid="delhi-unavailable" style={{ ...box, background: C.saffronTint, border: `1px solid ${C.saffron}` }}>
                    <strong style={{ color: C.ink }}>Delhi filing support isn&apos;t available yet.</strong>{' '}
                    Needle can&apos;t prepare or record a Delhi complaint for this account at the moment. Please contact your administrator.
                    Needle does not file or check Delhi grievances for you.
                </div>
            )}

            {(manualReferenceEnabled || filed) && (
                <div data-testid="delhi-honesty-note" style={box}>
                    <strong style={{ color: C.ink }}>Staff-assisted filing.</strong>{' '}
                    The Delhi portal asks for a CAPTCHA and a one-time password (OTP) every time, so a person must complete those steps on the official website.
                    Needle drafts the text and keeps the record; it does not submit anything to the portal and cannot read the portal&apos;s status.
                </div>
            )}

            {manualReferenceEnabled && !filed && (
                <div data-testid="delhi-step-prepare">
                    <div style={heading}>1 · Draft the worksheet</div>
                    <Button type="button" size="sm" variant="outline" disabled={prepBusy} onClick={handlePrepare}>
                        {prepBusy ? <Loader2 size={14} className="animate-spin" /> : (worksheet ? 'Draft again' : 'Draft worksheet with AI')}
                    </Button>
                    {worksheet && (
                        <div style={{ marginTop: 10 }}>
                            <CopyField label="Subject" value={worksheet.subject} />
                            <CopyField label="Description" value={worksheet.description} />
                            <div data-testid="delhi-ws-notes" style={{ ...box, fontSize: '0.75rem' }}>
                                {worksheet.department_note || 'Department/category: select them in the filing worksheet below; Needle does not choose them for you.'}
                                {' '}{worksheet.limits_note || ''}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {manualReferenceEnabled && !filed && (
                <DelhiFilingWorksheet
                    caseId={caseId}
                    govtCase={govtCase}
                    aiDraftDescription={worksheet?.description || ''}
                    onSaved={(outcome) => onRecorded?.(outcome)}
                />
            )}

            {manualReferenceEnabled && !filed && (
                <div data-testid="delhi-step-file">
                    <div style={heading}>2 · File on the official portal</div>
                    <Button type="button" size="sm" variant="outline" onClick={() => (fileTask ? handleOpenTask(fileTask) : openDelhiPortal())}>
                        Open official Delhi portal
                    </Button>
                    <span style={{ marginLeft: 8, fontSize: '0.75rem', color: C.ink3 }}>cmjansunwai.delhi.gov.in · opens in a new tab</span>
                    {contactNumber && (
                        <div data-testid="delhi-contact" style={{ ...box, marginTop: 8, fontSize: '0.75rem' }}>
                            Office mobile number on file for the OTP: <strong style={{ color: C.ink }}>{contactNumber}</strong>
                        </div>
                    )}
                    {fileTask && (
                        <ol data-testid="delhi-file-steps" style={{ ...box, marginTop: 8, paddingLeft: 28, listStyle: 'decimal' }}>
                            {fileTask.steps.map((s) => <li key={s}>{s}</li>)}
                        </ol>
                    )}
                </div>
            )}

            {manualReferenceEnabled && !filed && (
                <div data-testid="delhi-step-record">
                    <div style={heading}>3 · Record the complaint number</div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                        <Input
                            aria-label="Delhi portal reference number"
                            placeholder="Complaint number from the Delhi portal (digits only)"
                            inputMode="numeric"
                            value={refInput}
                            onChange={(e) => setRefInput(e.target.value)}
                            disabled={busy}
                            style={{ fontSize: '0.78125rem', flex: '1 1 180px' }}
                        />
                        <Button type="button" size="sm" disabled={busy || !refInput.trim()} onClick={handleSave}>
                            {busy ? <Loader2 size={14} className="animate-spin" /> : 'Save reference'}
                        </Button>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: C.ink3, marginTop: 4 }}>{DELHI_REFERENCE_RULE}</div>
                </div>
            )}

            {filed && (
                <div data-testid="delhi-filed">
                    <div style={box}>
                        <div>
                            Complaint number: <strong data-testid="delhi-saved-reference" style={{ color: C.ink }}>{storedRef}</strong>
                            {' · '}Status: <strong style={{ color: C.ink }}>Submitted (recorded by staff)</strong>
                        </div>
                        <div style={{ marginTop: 4, fontSize: '0.75rem', color: C.ink3 }}>
                            This number was entered by staff. Needle has not verified it with the portal and does not check Delhi status automatically.
                        </div>
                    </div>
                    {['status', 'reminder', 'feedback'].map((k) => taskByKey(k)).filter(Boolean).map((task) => (
                        <div key={task.key} data-testid={`delhi-task-${task.key}`} style={{ ...box, marginTop: 8 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                                <Button type="button" size="sm" variant="outline" onClick={() => handleOpenTask(task)}>{task.label}</Button>
                                <span style={{ fontSize: '0.75rem', color: C.ink3 }}>{task.available}</span>
                            </div>
                            <div style={{ fontSize: '0.75rem', marginTop: 6 }}>
                                The portal will ask for: {task.inputs.join(' · ')}.
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {message && (
                <div role={message.tone === 'error' ? 'alert' : 'status'} style={{ fontSize: '0.75rem', padding: '8px 10px', ...toneStyle(message.tone) }}>
                    {message.text}
                </div>
            )}
        </div>
    );
}
