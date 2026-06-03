'use client';

import Link from 'next/link';

const LINKS = [
    {
        title: 'Seat Geography Upload',
        body: 'Upload or refine the seat-scoped geography dataset that powers matching, assembly resolution, and map generation.',
        href: '/dashboard/shared-geography/workspace',
        cta: 'Open uploader',
    },
    {
        title: 'Geography Rules',
        body: 'Review seat-scoped routing overrides, conflict handling, and exception rules.',
        href: '/dashboard/shared-geography/rules',
        cta: 'Open rules',
    },
    {
        title: 'Seat Maps',
        body: 'Open map readiness and generation workflows once geography quality is confirmed.',
        href: '/dashboard/seat-maps',
        cta: 'Open seat maps',
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

export default function SharedGeographyPage() {
    return (
        <div className="space-y-6">
            <div className="admin-domain-hero">
                <div className="cn-eyebrow">Shared Geography</div>
                <h2 className="cn-h1 mt-3">Geography should be managed once per seat and reused safely across tenants.</h2>
                <p className="cn-body mt-3 max-w-3xl text-sm">
                    This domain is where operators keep locality structure clean, resolve ambiguity early, and make sure every downstream workflow sees
                    the same trustworthy seat geography.
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
