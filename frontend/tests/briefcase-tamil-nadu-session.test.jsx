import { describe, it, expect } from 'vitest';

import {
    isTamilNaduLiveSessionActive,
    isTamilNaduResolvedPortal,
} from '@/components/briefcase/BriefcaseCaseModal';

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
