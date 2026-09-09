import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
    isTamilNaduLiveSessionActive,
    isTamilNaduResolvedPortal,
    resolveGovtStatusCheckAction,
    scopeLiveSessionToCase,
    shouldShowGovtVerificationWorkspace,
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
        expect(modalSource).toMatch(/const action = govtSyncRef\.current\?\.checkGovernmentStatus\(\);[\s\S]*?if \(action === 'verification_required'\) \{[\s\S]*?scrollIntoView/);
    });

    it('keeps live-browser startup behind the explicit Tamil Nadu verification button', () => {
        expect(modalSource).toMatch(/onClick=\{handleStartTnStatusSession\}[\s\S]*?'Verify access'/);
        expect(modalSource).toContain('govtSyncRef.current?.checkGovernmentStatus()');
    });
});

describe('shouldShowGovtVerificationWorkspace', () => {
    it('keeps filed TN cases compact outside explicit verification', () => {
        expect(shouldShowGovtVerificationWorkspace({
            isTamilNadu: true,
            alreadyFiled: true,
            verificationMode: false,
        })).toBe(false);
    });

    it('shows the TN browser workspace only during explicit verification', () => {
        expect(shouldShowGovtVerificationWorkspace({
            isTamilNadu: true,
            alreadyFiled: true,
            verificationMode: true,
        })).toBe(true);
    });

    it('does not change existing-state or unfiled filing workspaces', () => {
        expect(shouldShowGovtVerificationWorkspace({
            isTamilNadu: false,
            alreadyFiled: true,
            verificationMode: false,
        })).toBe(true);
        expect(shouldShowGovtVerificationWorkspace({
            isTamilNadu: true,
            alreadyFiled: false,
            verificationMode: false,
        })).toBe(true);
    });

    it('closes the promoted browser session before returning to compact status UI', () => {
        expect(modalSource).toMatch(/if \(result\.promoted\) \{[\s\S]*?await handleCloseLive\(\)/);
        expect(modalSource).toContain('if (isTamilNaduLiveSessionActive(session.portal_name)) setTnVerificationMode(false)');
    });

    it('only reconnects a discovered TN session inside the explicit verification handler', () => {
        const startHandler = modalSource.match(/async function handleStartTnStatusSession\(\) \{[\s\S]*?\n    \}/)?.[0] || '';
        expect(startHandler).toContain('setTnVerificationMode(true)');
        expect(startHandler).toContain('setLive(existing)');
        expect(modalSource).toContain('hostedSessions.length > 0 && showGovtVerificationWorkspace');
        expect(modalSource).toContain('currentLiveSession && showGovtVerificationWorkspace');
    });
});

describe('case-scoped live-session lifecycle', () => {
    const caseASession = {
        case_id: 101,
        session_id: 'case-a-session',
        ws_path: '/api/govt/session/case-a-session/stream',
        portal_name: 'Tamil Nadu CM Helpline (Mudhalvarin Mugavari)',
    };

    it('rejects Case A liveSession immediately when rendering Case B', () => {
        expect(scopeLiveSessionToCase(caseASession, 101)).toBe(caseASession);
        expect(scopeLiveSessionToCase(caseASession, 202)).toBeNull();
    });

    it('cannot pass a stale Case A session or ws_path to Case B browser rendering', () => {
        const caseBLiveSession = scopeLiveSessionToCase(caseASession, 202);
        expect(caseBLiveSession).toBeNull();
        expect(caseBLiveSession?.ws_path).toBeUndefined();
        expect(modalSource).toContain('currentLiveSession && showGovtVerificationWorkspace');
        expect(modalSource).toContain('wsPath={currentLiveSession.ws_path}');
    });

    it('clears both liveSession and liveSessionRef at the start of the caseId effect', () => {
        const lifecycleEffect = modalSource.match(/useEffect\(\(\) => \{\n        if \(!caseId\) return;[\s\S]*?\n    \}, \[caseId\]\);/)?.[0] || '';
        expect(lifecycleEffect).toMatch(/if \(!caseId\) return;\n        setLive\(null\);/);
        expect(modalSource).toMatch(/function setLive\(session\) \{[\s\S]*?liveSessionRef\.current = scopedSession;[\s\S]*?setLiveSession\(scopedSession\)/);
    });

    it('preserves cleanup of the previous case backend session', () => {
        expect(modalSource).toMatch(/return \(\) => \{[\s\S]*?liveSessionRef\.current[\s\S]*?\/govt\/session\/\$\{session\.session_id\}\/close/);
    });

    it('stamps newly started sessions with the current case before attachment', () => {
        expect(modalSource).toContain('? { ...session, case_id: caseId }');
        expect(scopeLiveSessionToCase({ ...caseASession, case_id: 202 }, 202)?.session_id).toBe('case-a-session');
    });

    it('routes the journey refresh control to status checking rather than escalation', () => {
        expect(modalSource).toContain('onRefresh={handleGovernmentStatusClick}');
        expect(modalSource).not.toContain('onRefresh={handleEscalateClick}');
    });
});
