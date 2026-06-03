'use client';

import Link from 'next/link';

const LINKS = [
    {
        title: 'Staff Management',
        body: 'Manage non-primary tenant staff accounts, role coverage, and operational staffing hygiene.',
        href: '/dashboard/staff-access/users',
        cta: 'Open staff management',
    },
    {
        title: 'Audit Log',
        body: 'Review administrative actions, permission changes, and access history from the audit log.',
        href: '/dashboard/staff-access/audit',
        cta: 'Open audit log',
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

export default function StaffAccessPage() {
    return (
        <div className="space-y-6">
            <div className="rounded-2xl border border-[#dce8e1] bg-[#f8fbf9] p-5">
                <div className="text-xs font-bold uppercase tracking-[0.18em] text-[#6b7f76]">Access Control</div>
                <h2 className="mt-2 text-xl font-bold text-[#1a2e28]">Staff and access controls should live together.</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-[#6b7f76]">
                    This domain keeps user management and access traceability in one place so admins can onboard staff, review changes, and investigate
                    issues without bouncing between disconnected tools.
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
