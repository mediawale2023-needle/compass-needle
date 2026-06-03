'use client';

import Link from 'next/link';

const LINKS = [
    {
        title: 'All Accounts',
        body: 'Review every account, linked seat, readiness state, and drill-in detail from the account registry.',
        href: '/dashboard/accounts/registry',
        cta: 'Open account registry',
    },
    {
        title: 'Create Account',
        body: 'Create new MP, MLA, or aspirant accounts with the canonical onboarding flow.',
        href: '/dashboard/accounts/new',
        cta: 'Create account',
    },
    {
        title: 'Setup Workflows',
        body: 'Track launch blockers, readiness gaps, and follow-up work from the operations overview.',
        href: '/dashboard',
        cta: 'Review overview queue',
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

export default function AccountsPage() {
    return (
        <div className="space-y-6">
            <div className="admin-domain-hero">
                <div className="cn-eyebrow">Account Lifecycle</div>
                <h2 className="cn-h1 mt-3">Accounts is the primary control surface for tenant onboarding and readiness.</h2>
                <p className="cn-body mt-3 max-w-3xl text-sm">
                    Use this domain to create accounts, review setup progress, inspect linked seats, and move tenants from draft setup into live
                    operations without jumping across unrelated tools.
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
