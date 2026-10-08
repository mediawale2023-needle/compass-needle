import { describe, expect, it } from 'vitest';
import { activeNavItem, breadcrumbFor, NAV_GROUPS } from '@/lib/admin-nav';

const active = (path) => activeNavItem(path)?.id ?? null;

describe('admin navigation ownership', () => {
    it('keeps the approved destination order', () => {
        expect(NAV_GROUPS.map((g) => g.label)).toEqual(['Command', 'Customers', 'Operations', 'Platform', 'Administration']);
        expect(NAV_GROUPS.flatMap((g) => g.items.map((i) => i.label))).toEqual([
            'Command Centre', 'Accounts', 'Onboarding', 'Cases', 'Messaging', 'Data & Geography', 'System', 'People & Access', 'Audit & Settings',
        ]);
    });

    it.each([
        ['/dashboard', 'command'],
        ['/dashboard/accounts', 'accounts'],
        ['/dashboard/accounts/registry', 'accounts'],
        ['/dashboard/mps/42', 'accounts'],
        ['/dashboard/accounts/new', 'onboarding'],
        ['/dashboard/mps/new', 'onboarding'],
        ['/dashboard/mps/42/setup', 'onboarding'],
        ['/dashboard/cases-intelligence/explorer', 'cases'],
        ['/dashboard/cases-intelligence/engine', 'cases'],
        ['/dashboard/constituency', 'cases'],
        ['/dashboard/system/whatsapp', 'messaging'],
        ['/dashboard/system/whatsapp-inbound', 'messaging'],
        ['/dashboard/seats', 'geography'],
        ['/dashboard/seats/mp:Aligarh', 'geography'],
        ['/dashboard/shared-geography/workspace', 'geography'],
        ['/dashboard/seat-maps', 'geography'],
        ['/dashboard/system', 'system'],
        ['/dashboard/system/health', 'system'],
        ['/dashboard/system/jobs', 'system'],
        ['/dashboard/system/parliament-sync', 'system'],
        ['/dashboard/staff-access/users', 'people'],
        ['/dashboard/staff-access/audit', 'audit'],
        ['/dashboard/system/settings', 'audit'],
        ['/dashboard/system/announcements', 'audit'],
    ])('%s belongs to %s', (path, id) => {
        expect(active(path)).toBe(id);
    });

    it('never lights System for Messaging routes', () => {
        expect(active('/dashboard/system/whatsapp')).not.toBe('system');
    });

    it('builds breadcrumbs from route structure only', () => {
        expect(breadcrumbFor('/dashboard').map((c) => c.label)).toEqual(['Command', 'Command Centre']);
        expect(breadcrumbFor('/dashboard/mps/7').map((c) => c.label)).toEqual(['Customers', 'Accounts', 'Account 360']);
        expect(breadcrumbFor('/dashboard/system/whatsapp-inbound').map((c) => c.label)).toEqual(['Operations', 'Messaging', 'Inbound']);
        expect(breadcrumbFor('/nowhere')).toEqual([{ label: 'Needle', href: '/dashboard' }]);
    });
});
