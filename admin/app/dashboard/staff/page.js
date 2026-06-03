import { redirect } from 'next/navigation';

export default function StaffLegacyRedirect() {
    redirect('/dashboard/staff-access/users');
}
