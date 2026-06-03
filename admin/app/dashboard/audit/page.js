import { redirect } from 'next/navigation';

export default function AuditLegacyRedirect() {
    redirect('/dashboard/staff-access/audit');
}
