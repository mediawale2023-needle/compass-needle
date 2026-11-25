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

    it('maps up to four articles with source, link and age', () => {
        const articles = Array.from({ length: 6 }, (_, i) => ({ title: `T${i}`, source: 'Pudhari', link: `https://n/${i}`, published: '2026-11-24T06:00:00' }));
        const { media } = mapOverviewResponse({}, null, { articles });
        expect(media).toHaveLength(4);
        expect(media[0]).toMatchObject({ title: 'T0', source: 'Pudhari', href: 'https://n/0' });
        expect(typeof media[0].age).toBe('string');
    });
});
