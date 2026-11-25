import { describe, expect, it } from 'vitest';
import { mapPresence } from '@/lib/dashboard-mappers';
import { presenceRows } from '@/components/dashboard/OverviewDashboard';

const loc = (name, people) => ({ name, people, complaints: people, status: people >= 10 ? 'strong' : people >= 3 ? 'growing' : people ? 'thin' : 'none' });

describe('presence map', () => {
    it('maps the API shape and defaults unknown statuses safely', () => {
        const p = mapPresence({ localities: [{ name: 'A', people: 2, status: 'weird' }], with_presence: 1, total: 4, gazetteer_known: true });
        expect(p).toEqual({ localities: [{ name: 'A', people: 2, complaints: 0, status: 'none' }], withPresence: 1, total: 4, gazetteerKnown: true });
        expect(mapPresence(undefined)).toEqual({ localities: [], withPresence: 0, total: 0, gazetteerKnown: false });
    });

    it('collapsed view keeps the strongest plus up to two localities with no contact', () => {
        const all = [loc('A', 20), loc('B', 12), loc('C', 9), loc('D', 5), loc('E', 3), loc('F', 1), loc('G', 0), loc('H', 0), loc('I', 0)];
        const rows = presenceRows(all, false).map((r) => r.name);
        expect(rows).toEqual(['A', 'B', 'C', 'D', 'G', 'H']);
        expect(presenceRows(all, true)).toHaveLength(9);
        expect(presenceRows([loc('A', 4), loc('Z', 0)], false).map((r) => r.name)).toEqual(['A', 'Z']);
    });
});
