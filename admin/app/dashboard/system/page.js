'use client';

import Link from 'next/link';

const LINKS = [
    {
        title: 'Tenant Health',
        body: 'Monitor platform and tenant health, rollout blockers, and readiness state from one health surface.',
        href: '/dashboard/system/health',
        cta: 'Open health',
    },
    {
        title: 'Announcements',
        body: 'Manage global operator-to-dashboard communication and banner messaging.',
        href: '/dashboard/system/announcements',
        cta: 'Open announcements',
    },
    {
        title: 'Settings',
        body: 'Manage administrator settings, editor controls, and platform-wide configuration.',
        href: '/dashboard/system/settings',
        cta: 'Open settings',
    },
    {
        title: 'Parliament Sync',
        body: 'Run and review parliament sync workflows that support the broader platform data layer.',
        href: '/dashboard/system/parliament-sync',
        cta: 'Open sync tools',
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

export default function SystemPage() {
    return (
        <div className="space-y-6">
            <div className="rounded-2xl border border-[#dce8e1] bg-[#f8fbf9] p-5">
                <div className="text-xs font-bold uppercase tracking-[0.18em] text-[#6b7f76]">Platform Control</div>
                <h2 className="mt-2 text-xl font-bold text-[#1a2e28]">System is the home for platform-wide health, settings, communication, and sync.</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-[#6b7f76]">
                    Use this domain for platform-wide controls that should stay distinct from seat, geography, and account workflows: health, messaging,
                    settings, and sync operations.
                </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
                {LINKS.map((item) => (
                    <Card key={item.title} {...item} />
                ))}
            </div>
        </div>
    );
}
