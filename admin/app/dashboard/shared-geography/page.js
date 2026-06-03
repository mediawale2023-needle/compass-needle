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
            className="block rounded-2xl border border-[#e2ebe5] bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
            style={{ textDecoration: 'none' }}
        >
            <div className="text-base font-semibold text-[#1a2e28]">{title}</div>
            <p className="mt-2 text-sm leading-6 text-[#6b7f76]">{body}</p>
            <div className="mt-4 text-sm font-semibold text-[#006a4d]">{cta} →</div>
        </Link>
    );
}

export default function SharedGeographyPage() {
    return (
        <div className="space-y-6">
            <div className="rounded-2xl border border-[#dce8e1] bg-[#f8fbf9] p-5">
                <div className="text-xs font-bold uppercase tracking-[0.18em] text-[#6b7f76]">Shared Geography</div>
                <h2 className="mt-2 text-xl font-bold text-[#1a2e28]">Geography should be managed once per seat and reused safely across tenants.</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-[#6b7f76]">
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
