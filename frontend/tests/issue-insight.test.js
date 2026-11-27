import { describe, expect, it } from 'vitest';
import { changeLabel, draftHref, headline, insight, moves, newsCount, verdict } from '@/lib/issueInsight';

const base = {
    issue: 'Roads & Bridges', complaints: 32, previous: 19, people: 27, locality_count: 5, quadrant: 'plank',
    localities: [{ name: 'Tilakwadi', complaints: 11 }, { name: 'Khasbag', complaints: 5 }],
    open_over_30_days: 22, oldest_open_days: 168, department: 'Public Works Dept', filed: 8, filed_resolved: 2, languages: [],
};

describe('issue insight wording', () => {
    it('labels change as a percentage only on a real base', () => {
        expect(changeLabel(base)).toBe('+68%');
        expect(changeLabel({ ...base, complaints: 9, previous: 2 })).toBe('2 → 9');
        expect(changeLabel({ ...base, complaints: 2, previous: 0 })).toBe('new');
        expect(changeLabel({ ...base, complaints: 9, previous: 10 })).toBe('-10%');
    });

    it('builds the headline from the campaign plank and the fastest riser', () => {
        const h = headline([base, { ...base, issue: 'Theft & Safety', quadrant: 'flash', complaints: 9, previous: 2 }], 90);
        expect(h).toMatchObject({ lead: 'Roads & Bridges', riser: { name: 'theft & safety', from: 2, to: 9, days: 90 } });
        expect(headline([{ ...base, quadrant: 'watch' }], 30)).toMatchObject({ leadText: 'is what people raise most', riser: null });
        expect(headline([], 30)).toBeNull();
    });

    it('changes verdict and moves for aspirant vs sitting member', () => {
        expect(verdict(base, false)).toBe('Own this issue');
        expect(verdict(base, true)).toBe('Fix this before it becomes the story');
        expect(moves(base, false)[0]).toEqual(['Public hearing in Tilakwadi', '34% of these complaints come from there.']);
        expect(moves(base, true)[0][0]).toBe('Site visit with Public Works Dept in Tilakwadi');
        expect(moves({ ...base, quadrant: 'watch' }, false)).toHaveLength(1);
    });

    it('writes the read with the office facts and news count', () => {
        const text = insight(base, 90, 2);
        expect(text).toContain('32 complaints from 27 people in 5 localities, up 68% on the previous 90 days.');
        expect(text).toContain('22 complaints have waited over a month.');
        expect(text).toContain('Public Works Dept: 2 of 8 filings resolved.');
        expect(text).toContain('Local papers have carried it 2 times.');
    });

    it('counts tagged news and prefills the drafter', () => {
        expect(newsCount(base, [{ issue: 'Roads & Bridges' }, { issue: 'Water' }, null])).toBe(1);
        expect(newsCount(base, null)).toBeNull();
        const href = draftHref(base, false, 90);
        const q = new URLSearchParams(href.split('?')[1]);
        expect(q.get('recipient')).toBe('Public Works Dept');
        expect(q.get('context')).toContain('Tilakwadi (11)');
    });
});
