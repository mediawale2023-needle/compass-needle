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
            className="admin-domain-card"
            style={{ textDecoration: 'none' }}
        >
            <div className="cn-h3">{title}</div>
            <p className="cn-body mt-2 text-sm">{body}</p>
            <div className="admin-domain-card-arrow mt-4">{cta} →</div>
        </Link>
    );
}

export default function StaffAccessPage() {
    return (
        <div className="space-y-6">
            <div className="admin-domain-hero">
                <div className="cn-eyebrow">Access Control</div>
                <h2 className="cn-h1 mt-3">Staff and access controls should live together.</h2>
                <p className="cn-body mt-3 max-w-3xl text-sm">
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
