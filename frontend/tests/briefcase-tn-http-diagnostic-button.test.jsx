import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, it, expect } from 'vitest';

import { isTnHttpDiagnosticProofCase } from '@/components/briefcase/BriefcaseCaseModal';

// TEMPORARY test file for the TEMPORARY TN HTTP-diagnostic "run once" button
// (Phase 1 controlled-proof only — see PROJECT_MEMORY.md). Delete this file
// alongside the button/handler/constant it tests once the controlled proof
// is complete and reviewed.
//
// This repo's established convention is pure-function unit tests, not full
// component rendering (see the other frontend/tests/*.test.jsx files) —
// GovtSyncSection itself is an internal, unexported component. So:
//   - the gating rule ("renders only for case 3563") is tested as a real,
//     exported, pure function call — the render branch is a one-line
//     `isTnHttpDiagnosticProofCase(caseId) && (...)`, so exercising the
//     function IS exercising the actual gate;
//   - "uses the existing API client" / "never touches a token or
//     session_id" are verified by reading the component's own source text
//     and asserting the exact, narrow shape of the new code — no separate,
//     hand-written implementation to drift out of sync with the real file.

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const COMPONENT_SOURCE = fs.readFileSync(
    path.join(__dirname, '..', 'components', 'briefcase', 'BriefcaseCaseModal.jsx'),
    'utf8',
);

describe('isTnHttpDiagnosticProofCase — TN HTTP-diagnostic button gate', () => {
    it('is true only for case 3563', () => {
        expect(isTnHttpDiagnosticProofCase(3563)).toBe(true);
    });

    it('is true for the string form of the same id (case_id can arrive as either)', () => {
        expect(isTnHttpDiagnosticProofCase('3563')).toBe(true);
    });

    it('is false for every other case id, including neighbors', () => {
        for (const other of [1, 3562, 3564, 40, 20, 0, -1]) {
            expect(isTnHttpDiagnosticProofCase(other)).toBe(false);
        }
    });

    it('is false for null/undefined/non-numeric input, never throws', () => {
        expect(isTnHttpDiagnosticProofCase(null)).toBe(false);
        expect(isTnHttpDiagnosticProofCase(undefined)).toBe(false);
        expect(isTnHttpDiagnosticProofCase('not-a-number')).toBe(false);
        expect(isTnHttpDiagnosticProofCase({})).toBe(false);
    });
});

describe('TN HTTP-diagnostic button — source-level safety proofs', () => {
    // These inspect the actual shipped source text rather than a
    // hand-duplicated re-implementation, so they can't drift out of sync
    // with what's really rendered/invoked.

    function extractBlock(startMarker, endMarker) {
        const start = COMPONENT_SOURCE.indexOf(startMarker);
        expect(start, `could not find "${startMarker}" in BriefcaseCaseModal.jsx`).toBeGreaterThan(-1);
        const end = COMPONENT_SOURCE.indexOf(endMarker, start);
        expect(end, `could not find "${endMarker}" after "${startMarker}"`).toBeGreaterThan(-1);
        return COMPONENT_SOURCE.slice(start, end);
    }

    const handlerBlock = extractBlock(
        'async function handleRunTnHttpDiagnostic()',
        'async function handleSubmitRef()',
    );
    const renderBlock = extractBlock(
        'isTnHttpDiagnosticProofCase(caseId) &&',
        '{locked ? (',
    );

    it('the render branch is gated by isTnHttpDiagnosticProofCase(caseId), not a hardcoded literal repeated elsewhere', () => {
        expect(renderBlock).toContain('isTnHttpDiagnosticProofCase(caseId)');
    });

    it('invokes the existing authenticated API client (apiPost) — never a raw fetch, never a manually-built Authorization header', () => {
        expect(handlerBlock).toContain('apiPost(`/api/cases/${caseId}/govt/tamil-nadu/diagnostic/run`');
        expect(handlerBlock).not.toContain('fetch(');
        expect(handlerBlock).not.toContain('Authorization');
        expect(handlerBlock).not.toContain('getAuthToken');
    });

    it('never references a session_id anywhere in the handler or render block', () => {
        expect(handlerBlock.toLowerCase()).not.toContain('session_id');
        expect(renderBlock.toLowerCase()).not.toContain('session_id');
    });

    it('never logs anything to the console in the handler', () => {
        expect(handlerBlock).not.toContain('console.');
    });

    it('renders only the API response itself (via JSON.stringify), never an additional constructed field', () => {
        expect(renderBlock).toContain('JSON.stringify(tnHttpDiagnosticResult');
    });

    it('requires an explicit confirmation with the exact specified copy before ever calling apiPost', () => {
        expect(handlerBlock).toContain('window.confirm(');
        expect(handlerBlock).toContain(
            'This will contact the Tamil Nadu portal using the currently authenticated live session and run the controlled HTTP-replay diagnostic for grievance 18968314. Run once?',
        );
        // The confirm() call and its early return must appear BEFORE the
        // apiPost call — an unconfirmed click must never reach the network.
        const confirmIndex = handlerBlock.indexOf('window.confirm(');
        const apiPostIndex = handlerBlock.indexOf('apiPost(');
        expect(confirmIndex).toBeGreaterThan(-1);
        expect(apiPostIndex).toBeGreaterThan(confirmIndex);
    });

    it('the button label matches the required exact copy', () => {
        expect(renderBlock).toContain('Run TN HTTP Diagnostic — ONE TIME');
    });

    it('never calls the diagnostic automatically — the button click is the only call site for this path', () => {
        const occurrences = COMPONENT_SOURCE.split('/govt/tamil-nadu/diagnostic/run').length - 1;
        // Exactly one occurrence: inside handleRunTnHttpDiagnostic, invoked
        // only from the button's onClick — no useEffect, no mount-time call.
        expect(occurrences).toBe(1);
        expect(handlerBlock).not.toMatch(/setTimeout|setInterval/);
    });

    it('never retries automatically on failure — the catch block only shows a toast, no re-invocation', () => {
        const catchIndex = handlerBlock.indexOf('} catch (e) {');
        expect(catchIndex).toBeGreaterThan(-1);
        const catchBlock = handlerBlock.slice(catchIndex);
        expect(catchBlock).not.toContain('handleRunTnHttpDiagnostic(');
    });
});
