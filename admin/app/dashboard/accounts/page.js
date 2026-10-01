'use client';

import Link from 'next/link';
import ProfileEditorPage from '@/components/admin-domains/accounts/ProfileEditorPage';
import { AdminPageHeader } from '@/components/admin-ui/AdminPrimitives';

// Accounts landing is data-first: show the account registry directly instead
// of a card page that only linked to it.
export default function AccountsPage() {
    return (
        <>
            <AdminPageHeader
                title="Account Registry"
                description="Find a customer account, review readiness, and continue into profile, access, geography, messaging, or launch work without losing context."
                actions={<Link href="/dashboard/accounts/new" className="btn-primary">Create account</Link>}
            />
            <ProfileEditorPage />
        </>
    );
}
