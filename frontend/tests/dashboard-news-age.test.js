import { describe, expect, it } from 'vitest';
import { mapOverviewResponse, newsAge } from '@/lib/dashboard-mappers';

const NOW = Date.parse('2026-11-25T09:00:00Z');

describe('local signals', () => {
    it('describes article age in plain words', () => {
        expect(newsAge('2026-11-25T06:00:00', NOW)).toBe('today');
        expect(newsAge('2026-11-24T06:00:00', NOW)).toBe('yesterday');
        expect(newsAge('2026-11-20T06:00:00Z', NOW)).toBe('5 days ago');
        expect(newsAge('', NOW)).toBe('');
        expect(newsAge('not a date', NOW)).toBe('');
    });

    it('maps up to eight tagged stories with source, link, age and tags', () => {
        const items = Array.from({ length: 10 }, (_, i) => ({ title: `T${i}`, source: 'Pudhari', link: `https://n/${i}`, published: '2026-11-24T06:00:00',
            localities: ['Tilakwadi'], issue: 'Roads & Bridges', linked: '3 complaints', relevance: 3 }));
        const { media, mediaLoaded } = mapOverviewResponse({}, null, { items });
        expect(mediaLoaded).toBe(true);
        expect(media).toHaveLength(8);
        expect(media[0]).toMatchObject({ title: 'T0', source: 'Pudhari', href: 'https://n/0', localities: ['Tilakwadi'], issue: 'Roads & Bridges', linked: '3 complaints', relevance: 3 });
        expect(typeof media[0].age).toBe('string');
    });

    it('treats untagged stories as relevant and reports when news has not loaded', () => {
        const { media } = mapOverviewResponse({}, null, { articles: [{ title: 'X', source: 'S' }] });
        expect(media[0]).toMatchObject({ localities: [], issue: null, linked: null, relevance: 2 });
        expect(mapOverviewResponse({}, null, null).mediaLoaded).toBe(false);
    });
});
