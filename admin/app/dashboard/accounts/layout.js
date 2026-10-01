import { AdminSectionNav } from '@/components/admin-ui/AdminPrimitives';

const ITEMS = [
    { label: 'Account Registry', href: '/dashboard/accounts' },
    { label: 'Create Account', href: '/dashboard/accounts/new' },
];

export default function AccountsLayout({ children }) {
    return <><AdminSectionNav label="Accounts" items={ITEMS} />{children}</>;
}
