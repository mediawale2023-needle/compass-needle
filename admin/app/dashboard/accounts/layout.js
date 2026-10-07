'use client';

import { usePathname } from 'next/navigation';
import { AdminSectionNav } from '@/components/admin-ui/AdminPrimitives';

const ITEMS = [
    { label: 'Account Registry', href: '/dashboard/accounts' },
    { label: 'Create Account', href: '/dashboard/accounts/new' },
];

// Onboarding is its own sidebar destination with a guided flow, so the
// registry tabs are not repeated above the stepper.
export default function AccountsLayout({ children }) {
    const pathname = usePathname();
    if (pathname === '/dashboard/accounts/new') return children;
    return <><AdminSectionNav label="Accounts" items={ITEMS} />{children}</>;
}
