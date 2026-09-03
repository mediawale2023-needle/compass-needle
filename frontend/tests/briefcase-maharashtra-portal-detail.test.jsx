import { describe, it, expect } from 'vitest';

import { formatGovtPortalDetailRows } from '@/components/briefcase/BriefcaseCaseModal';

// Regression guard for a real, previously-fixed bug (2026-08-25): this row
// list was hardcoded to Karnataka's portal_detail shape, so Maharashtra's
// own fields (district/office_contact/office_email/officer, extracted by
// modules/govt_sync/adapters/maharashtra_aaplesarkar.py's real captured
// result page) silently never rendered in Briefcase. Pin the fixed,
// generic shape so it can't regress back to a single-portal field list.
describe('formatGovtPortalDetailRows — Maharashtra fields', () => {
    it('renders Maharashtra-specific fields alongside the shared ones', () => {
        const rows = formatGovtPortalDetailRows({
            raw_portal_status: 'Submitted',
            portal_detail: {
                district: 'Buldhana',
                department: 'ग्राम विकास',
                office: 'RDDE Buldhana',
                officer: 'Shri Example Officer',
                office_contact: '9876543210',
                office_email: 'rdde.sec@nic.in',
            },
        });
        const byLabel = Object.fromEntries(rows);

        expect(byLabel['District']).toBe('Buldhana');
        expect(byLabel['Department']).toBe('ग्राम विकास');
        expect(byLabel['Office']).toBe('RDDE Buldhana');
        expect(byLabel['Officer']).toBe('Shri Example Officer');
        expect(byLabel['Office contact']).toBe('9876543210');
        expect(byLabel['Office email']).toBe('rdde.sec@nic.in');
        expect(byLabel['Portal status']).toBe('Submitted');
    });

    it('omits empty/missing fields rather than rendering blank rows', () => {
        const rows = formatGovtPortalDetailRows({
            raw_portal_status: 'Submitted',
            portal_detail: { district: 'Buldhana', officer: '' },
        });
        const labels = rows.map(([label]) => label);

        expect(labels).toContain('District');
        expect(labels).not.toContain('Officer');
        expect(labels).not.toContain('Office contact');
    });

    it('returns an empty list when there is no status check yet', () => {
        expect(formatGovtPortalDetailRows(null)).toEqual([]);
        expect(formatGovtPortalDetailRows(undefined)).toEqual([]);
    });
});
