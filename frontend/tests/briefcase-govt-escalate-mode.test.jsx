import { describe, it, expect } from 'vitest';

import { resolveGovtEscalateMode } from '@/components/briefcase/BriefcaseCaseModal';

// GovtSync filing simplification, PR2: "Escalate to Government Portal" must
// ALWAYS open the real government portal in a new local browser tab — never
// Needle's own remote Playwright/browser-session infrastructure — regardless
// of live_session_supported, live_automation_enabled, or any other portal
// config flag. This pins that contract at the exact decision point
// (resolveEscalateMode delegates to this pure, exported function) so a
// future change can't silently reintroduce a 'live' filing path.
//
// Portal shapes below mirror the real /api/govt-portal response contract and
// real modules/data/govt_portals.json rows (Rajasthan/Karnataka/Maharashtra/
// Tamil Nadu/CPGRAMS) — none of these URLs/flags are invented for the test.

const RAJASTHAN_PORTAL_DATA = {
    state: 'Rajasthan',
    supported: true,
    live_automation_enabled: true,
    portal: {
        id: 1, portal_name: 'Rajasthan Sampark', base_url: 'https://sampark.rajasthan.gov.in',
        otp_bound: true, portal_type: 'state_branded', ready: true,
        live_session_supported: true, entry_url: 'https://sampark.rajasthan.gov.in',
        otp_verification: { verified: false }, interactive_status_check: false,
    },
};

const KARNATAKA_PORTAL_DATA = {
    state: 'Karnataka',
    supported: true,
    live_automation_enabled: true,
    portal: {
        id: 2, portal_name: 'Karnataka Janaspandana (iPGRS)', base_url: 'https://ipgrs.karnataka.gov.in',
        otp_bound: true, portal_type: 'state_branded', ready: true,
        live_session_supported: true, entry_url: 'https://ipgrs.karnataka.gov.in',
        otp_verification: null, interactive_status_check: true,
    },
};

const MAHARASHTRA_PORTAL_DATA = {
    state: 'Maharashtra',
    supported: true,
    live_automation_enabled: true,
    portal: {
        id: 3, portal_name: 'Maharashtra Aaple Sarkar Grievance Redressal', base_url: 'https://grievances.maharashtra.gov.in',
        otp_bound: true, portal_type: 'state_branded', ready: true,
        // Maharashtra is the one real portal with live_session_supported=false
        // on file (network-level EC2 block) — must resolve the same as every
        // other portal now, not specially.
        live_session_supported: false, entry_url: 'https://grievances.maharashtra.gov.in',
        otp_verification: null, interactive_status_check: true,
    },
};

const TAMIL_NADU_PORTAL_DATA = {
    state: 'Tamil Nadu',
    supported: true,
    live_automation_enabled: true,
    portal: {
        id: 4, portal_name: 'Tamil Nadu CM Helpline (Mudhalvarin Mugavari)', base_url: 'https://cmhelpline.tnega.org',
        otp_bound: false, portal_type: 'state_branded', ready: true,
        live_session_supported: true, entry_url: 'https://cmhelpline.tnega.org',
        otp_verification: null, interactive_status_check: false,
    },
};

const CPGRAMS_FALLBACK_PORTAL_DATA = {
    state: '',
    supported: true,
    live_automation_enabled: true,
    portal: {
        id: 5, portal_name: 'CPGRAMS', base_url: 'https://pgportal.gov.in',
        otp_bound: false, portal_type: 'cpgrams', ready: true,
        live_session_supported: true, entry_url: 'https://pgportal.gov.in',
        otp_verification: null, interactive_status_check: false,
    },
};

const AUTOMATION_OFF_PORTAL_DATA = {
    ...RAJASTHAN_PORTAL_DATA,
    live_automation_enabled: false, // previously would have resolved to 'manual_worksheet'
};

const UNSUPPORTED_TENANT_DATA = {
    state: 'Unknown State',
    supported: false,
    live_automation_enabled: true,
    portal: null,
};

describe('resolveGovtEscalateMode — universal external filing (PR2)', () => {
    it('resolves Rajasthan to manual_redirect', () => {
        expect(resolveGovtEscalateMode(RAJASTHAN_PORTAL_DATA)).toBe('manual_redirect');
    });

    it('resolves Karnataka to manual_redirect', () => {
        expect(resolveGovtEscalateMode(KARNATAKA_PORTAL_DATA)).toBe('manual_redirect');
    });

    it('resolves Maharashtra (live_session_supported: false) to manual_redirect', () => {
        expect(resolveGovtEscalateMode(MAHARASHTRA_PORTAL_DATA)).toBe('manual_redirect');
    });

    it('resolves Tamil Nadu to manual_redirect', () => {
        expect(resolveGovtEscalateMode(TAMIL_NADU_PORTAL_DATA)).toBe('manual_redirect');
    });

    it('resolves the CPGRAMS fallback portal to manual_redirect', () => {
        expect(resolveGovtEscalateMode(CPGRAMS_FALLBACK_PORTAL_DATA)).toBe('manual_redirect');
    });

    it('resolves to manual_redirect even when live_automation_enabled is true (never live)', () => {
        expect(resolveGovtEscalateMode(RAJASTHAN_PORTAL_DATA)).toBe('manual_redirect');
    });

    it('resolves to manual_redirect when live_automation_enabled is false (never manual_worksheet)', () => {
        expect(resolveGovtEscalateMode(AUTOMATION_OFF_PORTAL_DATA)).toBe('manual_redirect');
    });

    it('resolves to manual_redirect for an unsupported tenant / null portal, never crashes', () => {
        expect(resolveGovtEscalateMode(UNSUPPORTED_TENANT_DATA)).toBe('manual_redirect');
        expect(resolveGovtEscalateMode(null)).toBe('manual_redirect');
        expect(resolveGovtEscalateMode(undefined)).toBe('manual_redirect');
    });

    it('never returns "live" for any input — the remote browser-session mode is unreachable', () => {
        const allShapes = [
            RAJASTHAN_PORTAL_DATA, KARNATAKA_PORTAL_DATA, MAHARASHTRA_PORTAL_DATA,
            TAMIL_NADU_PORTAL_DATA, CPGRAMS_FALLBACK_PORTAL_DATA, AUTOMATION_OFF_PORTAL_DATA,
            UNSUPPORTED_TENANT_DATA, null, undefined, {},
        ];
        for (const shape of allShapes) {
            expect(resolveGovtEscalateMode(shape)).not.toBe('live');
        }
    });

    it('never returns "manual_worksheet" for any input — every portal now opens externally', () => {
        const allShapes = [
            RAJASTHAN_PORTAL_DATA, KARNATAKA_PORTAL_DATA, MAHARASHTRA_PORTAL_DATA,
            TAMIL_NADU_PORTAL_DATA, CPGRAMS_FALLBACK_PORTAL_DATA, AUTOMATION_OFF_PORTAL_DATA,
            UNSUPPORTED_TENANT_DATA, null, undefined, {},
        ];
        for (const shape of allShapes) {
            expect(resolveGovtEscalateMode(shape)).not.toBe('manual_worksheet');
        }
    });
});
