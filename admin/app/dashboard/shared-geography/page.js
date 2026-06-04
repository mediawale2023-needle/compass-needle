'use client';

import Link from 'next/link';

const LINKS = [
    {
        title: 'Seat Geography Workspace',
        body: 'Upload or refine the seat-scoped geography dataset, maintain parent/sub-locality structure, and keep geography clean at the source.',
        href: '/dashboard/shared-geography/workspace',
        cta: 'Open workspace',
    },
    {
        title: 'Matching Corrections',
        body: 'Open the same workspace in tenant-aware mode to review manual corrections and resolver cleanup without jumping to a separate tool.',
        href: '/dashboard/shared-geography/workspace',
        cta: 'Open workspace',
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
