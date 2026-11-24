import { buildPartnerTheme, contrast, DEFAULT_BRAND_COLOR, initials } from '@/lib/partnerTheme';
import { bucketName, clientHealth, periodKey, periodLabel, periodQuery, toPeriod, windowLabel } from '@/lib/partnerFormat';

describe('partner theme engine', () => {
    it('keeps white button text and the brand as link colour for a dark brand', () => {
        const { vars, report } = buildPartnerTheme('#0F6E5C');
        expect(vars['--brand-fg']).toBe('#FFFFFF');
        expect(vars['--brand-ink']).toBe('#0F6E5C');
        expect(report.fgOnBrand).toBeGreaterThanOrEqual(4.5);
    });

    it('switches to dark button text and darkens links for a light brand', () => {
        const { vars, report } = buildPartnerTheme('#E8B624');
        expect(vars['--brand-fg']).toBe('#17181C');
        expect(report.fgOnBrand).toBeGreaterThanOrEqual(4.5);
        expect(report.brandOnWhite).toBeLessThan(4.5);
        expect(contrast(vars['--brand-ink'], '#FFFFFF')).toBeGreaterThanOrEqual(4.5);
    });

    it('falls back to the default colour for anything that is not a 6-digit hex', () => {
        for (const bad of [null, undefined, '', 'red', '#FFF', 'url(javascript:x)', '#12345G']) {
            expect(buildPartnerTheme(bad).vars['--brand']).toBe(DEFAULT_BRAND_COLOR);
        }
    });

    it('makes monogram initials from the brand name', () => {
        expect(initials('National Constituency Partners')).toBe('NP');
        expect(initials('Rajdhani')).toBe('RA');
        expect(initials('')).toBe('·');
    });
});

describe('client health', () => {
    const c = (summary, status = 'active') => ({ status, summary });
    it('flags many critical threads or a low resolution rate', () => {
        expect(clientHealth(c({ total: 40, critical: 5, resolution_rate: 0.9 })).level).toBe('attention');
        expect(clientHealth(c({ total: 40, critical: 0, resolution_rate: 0.4 })).level).toBe('attention');
        expect(clientHealth(c({ total: 40, critical: 1, resolution_rate: 0.9 })).level).toBe('watch');
        expect(clientHealth(c({ total: 40, critical: 0, resolution_rate: 0.9 })).level).toBe('ok');
    });
    it('does not judge resolution rate on fewer than 10 grievances', () => {
        expect(clientHealth(c({ total: 4, critical: 0, resolution_rate: 0 })).level).toBe('ok');
    });
    it('treats paused or summary-less clients as paused', () => {
        expect(clientHealth(c(null, 'paused')).level).toBe('paused');
        expect(clientHealth(c({ total: 1 }, 'paused')).level).toBe('paused');
    });
});

describe('reporting periods', () => {
    it('builds the partner API query for each kind of period', () => {
        expect(periodQuery({ kind: 'days', days: 90 })).toBe('days=90');
        expect(periodQuery(365)).toBe('days=365');
        expect(periodQuery({ kind: 'all' })).toBe('range=all');
        expect(periodQuery({ kind: 'custom', from: '2025-01-01', to: '2025-03-31' })).toBe('from=2025-01-01&to=2025-03-31');
        expect(periodQuery(undefined)).toBe('days=30');
    });
    it('gives stable keys and readable labels', () => {
        expect(periodKey({ kind: 'days', days: 7 })).toBe('d7');
        expect(periodKey(toPeriod(7))).toBe('d7');
        expect(periodLabel({ kind: 'all' })).toBe('All time');
        expect(periodLabel({ kind: 'days', days: 365 })).toBe('Last 12 months');
        expect(periodLabel({ kind: 'custom', from: '2025-01-01', to: '2025-03-31' })).toBe('1 Jan 2025 – 31 Mar 2025');
        expect(windowLabel({ kind: 'all', from: '2024-05-03' })).toBe('All time (since 3 May 2024)');
        expect(bucketName(30)).toBe('month');
    });
});
