'use client';

import Link from 'next/link';

const LINKS = [
    {
        title: 'Seat Maps',
        body: 'Manage boundary readiness, generated map workflows, and constituency visual state for each seat.',
        href: '/dashboard/seat-maps',
        cta: 'Open seat maps',
    },
    {
        title: 'Shared Geography',
        body: 'Review the seat-scoped geography datasets that power matching, routing, and map generation.',
        href: '/dashboard/shared-geography',
        cta: 'Open shared geography',
    },
    {
        title: 'Constituency Intelligence',
        body: 'Open seat-level intelligence and legacy reference context when operators need deeper constituency background.',
        href: '/dashboard/constituency',
        cta: 'Open constituency intelligence',
    },
];

function Card({ title, body, href, cta }) {
    return (
        <Link
            href={href}
            className="admin-domain-card"
            style={{ textDecoration: 'none' }}
        >
            <div className="cn-h3">{title}</div>
            <p className="cn-body mt-2 text-sm">{body}</p>
            <div className="admin-domain-card-arrow mt-4">{cta} →</div>
        </Link>
    );
}

export default function SeatsPage() {
    return (
        <div className="space-y-6">
            <div className="admin-domain-hero">
                <div className="cn-eyebrow">Seat Readiness</div>
                <h2 className="cn-h1 mt-3">Seats own the shared geography, shared boundaries, and shared maps used across tenants.</h2>
                <p className="cn-body mt-3 max-w-3xl text-sm">
                    Use this domain to understand whether a constituency is operationally ready: which tenants depend on it, whether geography is safe,
                    and whether boundary and map assets are ready for live use.
                </p>
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
                {LINKS.map((item) => (
                    <Card key={item.title} {...item} />
                ))}
            </div>
        </div>
    );
}
