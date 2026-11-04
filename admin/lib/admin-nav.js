/**
 * Admin information architecture: one source of truth for the sidebar,
 * the top-bar breadcrumb and route-to-destination matching.
 *
 * Every existing route stays reachable. A destination "owns" a set of route
 * prefixes so that deep pages (e.g. /dashboard/shared-geography/workspace)
 * highlight the destination the operator thinks of them as belonging to.
 * Matching is longest-prefix-wins, so /dashboard/system/whatsapp belongs to
 * Messaging even though /dashboard/system belongs to System.
 */

export const NAV_GROUPS = [
    {
        label: 'Command',
        items: [
            { id: 'command', href: '/dashboard', label: 'Command Centre', icon: 'command', exact: true },
        ],
    },
    {
        label: 'Customers',
        items: [
            { id: 'accounts', href: '/dashboard/accounts', label: 'Accounts', icon: 'accounts', owns: ['/dashboard/accounts', '/dashboard/mps', '/dashboard/profiles'], excludes: ['/dashboard/accounts/new', '/dashboard/mps/new'], excludePatterns: [/^\/dashboard\/mps\/[^/]+\/setup/] },
            { id: 'onboarding', href: '/dashboard/accounts/new', label: 'Onboarding', icon: 'onboarding', owns: ['/dashboard/accounts/new', '/dashboard/mps/new'], ownPatterns: [/^\/dashboard\/mps\/[^/]+\/setup/] },
        ],
    },
    {
        label: 'Operations',
        items: [
            { id: 'cases', href: '/dashboard/cases-intelligence/explorer', label: 'Cases', icon: 'cases', owns: ['/dashboard/cases-intelligence', '/dashboard/constituency', '/dashboard/knowledge', '/dashboard/brain', '/dashboard/analytics', '/dashboard/intelligence'] },
            { id: 'messaging', href: '/dashboard/system/whatsapp', label: 'Messaging', icon: 'messaging', owns: ['/dashboard/system/whatsapp', '/dashboard/system/whatsapp-inbound'] },
            { id: 'geography', href: '/dashboard/seats', label: 'Data & Geography', icon: 'geography', owns: ['/dashboard/seats', '/dashboard/shared-geography', '/dashboard/seat-maps', '/dashboard/geography', '/dashboard/rules'] },
        ],
    },
    {
        label: 'Platform',
        items: [
            { id: 'system', href: '/dashboard/system/health', label: 'System', icon: 'system', owns: ['/dashboard/system/health', '/dashboard/system/jobs', '/dashboard/system/parliament-sync', '/dashboard/health', '/dashboard/parliament-sync'], ownExact: ['/dashboard/system'] },
        ],
    },
    {
        label: 'Administration',
        items: [
            { id: 'people', href: '/dashboard/staff-access/users', label: 'People & Access', icon: 'people', owns: ['/dashboard/staff-access/users', '/dashboard/staff'], ownExact: ['/dashboard/staff-access'] },
            { id: 'audit', href: '/dashboard/staff-access/audit', label: 'Audit & Settings', icon: 'audit', owns: ['/dashboard/staff-access/audit', '/dashboard/audit', '/dashboard/system/settings', '/dashboard/system/announcements', '/dashboard/settings', '/dashboard/announcements'] },
        ],
    },
];

const ALL_ITEMS = NAV_GROUPS.flatMap((group) => group.items.map((item) => ({ ...item, group: group.label })));

function prefixMatches(pathname, prefix) {
    return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

/**
 * Returns a match score for an item: the length of the most specific rule
 * that claims the pathname, or -1 when the item does not claim it.
 */
function matchScore(pathname, item) {
    if (!pathname) return -1;
    if (item.exact) return pathname === item.href ? item.href.length : -1;
    if ((item.excludes || []).some((prefix) => prefixMatches(pathname, prefix))) return -1;
    if ((item.excludePatterns || []).some((pattern) => pattern.test(pathname))) return -1;
    let best = -1;
    for (const exact of item.ownExact || []) {
        if (pathname === exact) best = Math.max(best, exact.length);
    }
    for (const pattern of item.ownPatterns || []) {
        if (pattern.test(pathname)) best = Math.max(best, 1000);
    }
    for (const prefix of item.owns || [item.href]) {
        if (prefixMatches(pathname, prefix)) best = Math.max(best, prefix.length);
    }
    return best;
}

/** The single destination that owns this pathname, or null. */
export function activeNavItem(pathname) {
    let winner = null;
    let winnerScore = -1;
    for (const item of ALL_ITEMS) {
        const score = matchScore(pathname, item);
        if (score > winnerScore) {
            winner = item;
            winnerScore = score;
        }
    }
    return winnerScore >= 0 ? winner : null;
}

export function isNavItemActive(pathname, item) {
    return activeNavItem(pathname)?.id === item.id;
}

// Page-level labels for the breadcrumb leaf. Anything not listed falls back
// to the destination label, so the breadcrumb is never empty or invented.
const PAGE_LABELS = [
    [/^\/dashboard\/accounts\/registry/, 'Account registry'],
    [/^\/dashboard\/accounts\/new/, 'New account'],
    [/^\/dashboard\/mps\/new/, 'New account'],
    [/^\/dashboard\/mps\/[^/]+\/setup/, 'Launch setup'],
    [/^\/dashboard\/mps\/[^/]+$/, 'Account 360'],
    [/^\/dashboard\/cases-intelligence\/explorer/, 'Case Explorer'],
    [/^\/dashboard\/cases-intelligence\/knowledge/, 'Knowledge'],
    [/^\/dashboard\/cases-intelligence\/engine/, 'AI Engine'],
    [/^\/dashboard\/cases-intelligence\/analytics/, 'Usage Analytics'],
    [/^\/dashboard\/constituency/, 'Constituency Profiles'],
    [/^\/dashboard\/system\/whatsapp-inbound/, 'Inbound'],
    [/^\/dashboard\/seats\/[^/]+/, 'Seat detail'],
    [/^\/dashboard\/shared-geography\/workspace/, 'Geography workspace'],
    [/^\/dashboard\/shared-geography\/rules/, 'Geography rules'],
    [/^\/dashboard\/seat-maps/, 'Seat Maps'],
    [/^\/dashboard\/system\/parliament-sync/, 'Parliament Sync'],
    [/^\/dashboard\/system\/jobs/, 'Jobs'],
    [/^\/dashboard\/system\/announcements/, 'Announcements'],
    [/^\/dashboard\/system\/settings/, 'Settings'],
];

/**
 * Breadcrumb trail for the top bar: [group, destination, page?].
 * Built only from route structure — no data lookups.
 */
export function breadcrumbFor(pathname) {
    const item = activeNavItem(pathname);
    if (!item) return [{ label: 'Needle', href: '/dashboard' }];
    const trail = [{ label: item.group }, { label: item.label, href: item.href }];
    const leaf = PAGE_LABELS.find(([pattern]) => pattern.test(pathname || ''))?.[1];
    if (leaf && leaf !== item.label) trail.push({ label: leaf });
    return trail;
}

export const ALL_NAV_ITEMS = ALL_ITEMS;
