'use client';

import Link from 'next/link';

const LINKS = [
    {
        title: 'Case Intelligence',
        body: 'Review case health, operational risk, and grievance intelligence from the main case explorer.',
        href: '/dashboard/cases-intelligence/explorer',
        cta: 'Open case intelligence',
    },
    {
        title: 'Knowledge',
        body: 'Manage knowledge sync, answer readiness, and constituency data quality from one workspace.',
        href: '/dashboard/cases-intelligence/knowledge',
        cta: 'Open knowledge',
    },
    {
        title: 'AI Engine',
        body: 'Inspect AI diagnostics, intelligence readiness, and cross-system support signals.',
        href: '/dashboard/cases-intelligence/engine',
        cta: 'Open AI engine',
    },
    {
        title: 'Usage Analytics',
        body: 'Review platform usage and operator activity trends tied to case operations.',
        href: '/dashboard/cases-intelligence/analytics',
        cta: 'Open analytics',
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

export default function CasesIntelligencePage() {
    return (
        <div className="space-y-6">
            <div className="rounded-2xl border border-[#dce8e1] bg-[#f8fbf9] p-5">
                <div className="text-xs font-bold uppercase tracking-[0.18em] text-[#6b7f76]">Operational Intelligence</div>
                <h2 className="mt-2 text-xl font-bold text-[#1a2e28]">Cases and intelligence now live together as one operational domain.</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-[#6b7f76]">
                    Use this domain to move from raw case data to action: investigate spikes, check knowledge readiness, inspect AI support quality,
                    and understand usage trends without switching mental models.
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
