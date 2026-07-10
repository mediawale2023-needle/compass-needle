'use client';

import Link from 'next/link';
import ProfileEditorPage from '@/components/admin-domains/accounts/ProfileEditorPage';

// Accounts landing is data-first: show the account registry directly instead
// of a card page that only linked to it.
export default function AccountsPage() {
    return (
        <>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
                <Link href="/dashboard/accounts/new" className="btn-primary" style={{ textDecoration: 'none', fontSize: '0.78rem' }}>
                    + Create account
                </Link>
            </div>
            <ProfileEditorPage />
        </>
    );
}
