'use client';

import Link from 'next/link';

const LINKS = [
    {
        title: 'WhatsApp Operations',
        body: 'Inspect live Meta readiness, recent delivery failures, and retry outbound citizen replies from one queue.',
        href: '/dashboard/system/whatsapp',
        cta: 'Open WhatsApp ops',
    },
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
            className="admin-domain-card"
            style={{ textDecoration: 'none' }}
        >
            <div className="cn-h3">{title}</div>
            <p className="cn-body mt-2 text-sm">{body}</p>
            <div className="admin-domain-card-arrow mt-4">{cta} →</div>
        </Link>
    );
}

export default function SystemPage() {
    return (
        <div className="space-y-6">
            <div className="admin-domain-hero">
                <div className="cn-eyebrow">Platform Control</div>
                <h2 className="cn-h1 mt-3">System is the home for platform-wide health, settings, communication, and sync.</h2>
                <p className="cn-body mt-3 max-w-3xl text-sm">
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
