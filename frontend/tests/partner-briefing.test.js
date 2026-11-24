import { describe, expect, it } from 'vitest';
import { buildBriefing, changeLabel, changeTone, findRiser, funnelCallout, joinNames } from '@/lib/partnerBriefing';

const issue = (name, count, previous, locs = []) => ({ name, count, previous, trend: [], top_localities: locs.map(([n, c]) => ({ name: n, count: c })) });
const payload = (issues, received) => ({ momentum: { received: { now: received ?? issues.reduce((s, i) => s + i.count, 0) } }, issues });

describe('partner briefing text', () => {
    it('says so plainly when there were no complaints', () => {
        const b = buildBriefing(payload([], 0));
        expect(b.headline.lead).toBe('No complaints were received in this period.');
        expect(b.points).toEqual([]);
    });

    it('works without a comparison period (all time)', () => {
        const b = buildBriefing(payload([issue('Water', 10, null, [['Camp', 6]]), issue('Roads', 5, null)]));
        expect(b.headline.lead).toBe('Water accounts for 67% of complaints, concentrated in Camp.');
        expect(b.headline.emphasis).toBeNull();
        expect(b.points[0].strong).toBe('Water is the biggest issue: 10 complaints.');
        expect(b.points[1].strong).toBe('Roads is the next biggest issue');
        expect(b.text).not.toMatch(/pending|filed|resolved/i);
    });

    it('calls out the biggest issue itself when it is the one rising', () => {
        const b = buildBriefing(payload([issue('Water', 20, 10), issue('Roads', 2, 2)]));
        expect(b.headline.emphasis).toBe('These complaints doubled on the previous period.');
    });

    it('picks the sharpest qualifying rise and ignores tiny counts', () => {
        expect(findRiser([issue('A', 2, 0), issue('B', 6, 4), issue('C', 9, 3)])?.name).toBe('C');
        expect(findRiser([issue('A', 2, 0)])).toBeNull();
    });
});

describe('partner briefing helpers', () => {
    it('labels and colours changes by which direction is good', () => {
        expect(changeLabel(12, 31)).toBe('↓ 61%');
        expect(changeLabel(5, 0)).toBe('new');
        expect(changeLabel(5, null)).toBeNull();
        expect(changeTone(12, 31, 'up')).toBe('bad');
        expect(changeTone(96, 71, 'down')).toBe('bad');
        expect(changeTone(9, 7, 'up')).toBe('good');
        expect(changeTone(4, 4, 'up')).toBe('flat');
    });

    it('joins names in plain English', () => {
        expect(joinNames(['A'])).toBe('A');
        expect(joinNames(['A', 'B'])).toBe('A and B');
        expect(joinNames(['A', 'B', 'C'])).toBe('A, B and C');
    });

    it('flags filing first, then a pending majority, else progress', () => {
        expect(funnelCallout({ received: 10, ready_to_file: 1, oldest_ready_days: 1, pending: 0, action_taken: 10 }).body)
            .toBe('1 grievance is prepared for filing with government but not yet submitted; the oldest has waited 1 day. Raise this with the office this week.');
        expect(funnelCallout({ received: 10, ready_to_file: 0, pending: 6, action_taken: 4 }).title).toBe('Most grievances have no action yet.');
        expect(funnelCallout({ received: 10, ready_to_file: 0, pending: 2, action_taken: 8 }).tone).toBe('go');
        expect(funnelCallout({ received: 0 })).toBeNull();
    });
});
