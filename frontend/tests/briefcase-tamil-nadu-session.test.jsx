import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
    isTamilNaduLiveSessionActive,
    isTamilNaduResolvedPortal,
    resolveGovtStatusCheckAction,
} from '@/components/briefcase/BriefcaseCaseModal';

const modalSource = readFileSync(
    join(process.cwd(), 'components/briefcase/BriefcaseCaseModal.jsx'),
    'utf8',
);

// Regression pin for a real bug: isTamilNaduLiveSessionActive must reflect
// an ACTUALLY-OPEN live session, never a tenant's merely-resolved state.
// Falling back to resolved state made the action row show "Check Tamil Nadu
// status" before any session existed, and clicking it silently no-op'd
// (handleTamilNaduCheckStatus bails out with no session to check).
describe('isTamilNaduLiveSessionActive', () => {
    it('is false when no live session is open, even for a Tamil Nadu tenant', () => {
        // No liveSession at all — this must NOT be inferred true from the
        // tenant's resolved state (that was the bug).
        expect(isTamilNaduLiveSessionActive(undefined)).toBe(false);
        expect(isTamilNaduLiveSessionActive(null)).toBe(false);
        expect(isTamilNaduLiveSessionActive('')).toBe(false);
    });

    it('is true once a live session for Tamil Nadu is actually open', () => {
        expect(isTamilNaduLiveSessionActive('Tamil Nadu CM Helpline (Mudhalvarin Mugavari)')).toBe(true);
        expect(isTamilNaduLiveSessionActive('Mudhalvarin Mugavari')).toBe(true);
    });

    it('is false for a live session open on a different portal', () => {
        expect(isTamilNaduLiveSessionActive('Rajasthan Sampark')).toBe(false);
        expect(isTamilNaduLiveSessionActive('Karnataka iPGRS')).toBe(false);
        expect(isTamilNaduLiveSessionActive('Maharashtra Aaple Sarkar')).toBe(false);
    });
});

describe('isTamilNaduResolvedPortal', () => {
    it('is true when the tenant resolves to the Tamil Nadu portal, independent of any live session', () => {
        expect(isTamilNaduResolvedPortal('Tamil Nadu CM Helpline (Mudhalvarin Mugavari)', 'Tamil Nadu')).toBe(true);
        expect(isTamilNaduResolvedPortal(undefined, 'Tamil Nadu')).toBe(true);
    });

    it('is false for non-Tamil-Nadu tenants', () => {
        expect(isTamilNaduResolvedPortal('Rajasthan Sampark', 'Rajasthan')).toBe(false);
        expect(isTamilNaduResolvedPortal('Karnataka iPGRS', 'Karnataka')).toBe(false);
        expect(isTamilNaduResolvedPortal('Maharashtra Aaple Sarkar', 'Maharashtra')).toBe(false);
        expect(isTamilNaduResolvedPortal(undefined, undefined)).toBe(false);
    });
});

describe('resolveGovtStatusCheckAction', () => {
    it('routes verified Tamil Nadu access to the normal HTTP poll path', () => {
        expect(resolveGovtStatusCheckAction({
            isTamilNadu: true,
            tamilNaduCookieVerified: true,
            interactiveStatusCheck: false,
        })).toBe('poll');
    });

    it('routes unverified Tamil Nadu access to guidance without opening a live browser', () => {
        expect(resolveGovtStatusCheckAction({
            isTamilNadu: true,
            tamilNaduCookieVerified: false,
            interactiveStatusCheck: false,
        })).toBe('verification_required');
    });

    it('preserves the existing interactive status path for configured non-TN portals', () => {
        expect(resolveGovtStatusCheckAction({
            isTamilNadu: false,
            tamilNaduCookieVerified: false,
            interactiveStatusCheck: true,
        })).toBe('interactive');
    });

    it('wires the right-side status CTA to status checking, not escalation', () => {
        expect(modalSource).toContain("cta: 'Check government status', onAction: handleGovernmentStatusClick");
        expect(modalSource).not.toContain("cta: 'Check government status', onAction: handleEscalateClick");
    });

    it('keeps live-browser startup behind the explicit Tamil Nadu verification button', () => {
        expect(modalSource).toMatch(/onClick=\{handleStartTnStatusSession\}[\s\S]*?'Verify on Tamil Nadu portal'/);
        expect(modalSource).toContain('govtSyncRef.current?.checkGovernmentStatus()');
    });
});
