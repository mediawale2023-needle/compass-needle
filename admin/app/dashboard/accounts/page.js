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
            className="block rounded-2xl border border-[#e2ebe5] bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
            style={{ textDecoration: 'none' }}
        >
            <div className="text-base font-semibold text-[#1a2e28]">{title}</div>
            <p className="mt-2 text-sm leading-6 text-[#6b7f76]">{body}</p>
            <div className="mt-4 text-sm font-semibold text-[#006a4d]">{cta} →</div>
        </Link>
    );
}

export default function AccountsPage() {
    return (
        <div className="space-y-6">
            <div className="rounded-2xl border border-[#dce8e1] bg-[#f8fbf9] p-5">
                <div className="text-xs font-bold uppercase tracking-[0.18em] text-[#6b7f76]">Account Lifecycle</div>
                <h2 className="mt-2 text-xl font-bold text-[#1a2e28]">Accounts is the primary control surface for tenant onboarding and readiness.</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-[#6b7f76]">
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
