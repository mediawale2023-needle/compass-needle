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
            className="admin-domain-card"
            style={{ textDecoration: 'none' }}
        >
            <div className="cn-h3">{title}</div>
            <p className="cn-body mt-2 text-sm">{body}</p>
            <div className="admin-domain-card-arrow mt-4">{cta} →</div>
        </Link>
    );
}

export default function CasesIntelligencePage() {
    return (
        <div className="space-y-6">
            <div className="admin-domain-hero">
                <div className="cn-eyebrow">Operational Intelligence</div>
                <h2 className="cn-h1 mt-3">Cases and intelligence now live together as one operational domain.</h2>
                <p className="cn-body mt-3 max-w-3xl text-sm">
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
