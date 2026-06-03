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
            className="block rounded-2xl border border-[#e2ebe5] bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
            style={{ textDecoration: 'none' }}
        >
            <div className="text-base font-semibold text-[#1a2e28]">{title}</div>
            <p className="mt-2 text-sm leading-6 text-[#6b7f76]">{body}</p>
            <div className="mt-4 text-sm font-semibold text-[#006a4d]">{cta} →</div>
        </Link>
    );
}

export default function SeatsPage() {
    return (
        <div className="space-y-6">
            <div className="rounded-2xl border border-[#dce8e1] bg-[#f8fbf9] p-5">
                <div className="text-xs font-bold uppercase tracking-[0.18em] text-[#6b7f76]">Seat Readiness</div>
                <h2 className="mt-2 text-xl font-bold text-[#1a2e28]">Seats own the shared geography, shared boundaries, and shared maps used across tenants.</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-[#6b7f76]">
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
