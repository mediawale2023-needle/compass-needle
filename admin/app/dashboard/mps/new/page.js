import { redirect } from 'next/navigation';

export default function NewAccountLegacyRedirect() {
    redirect('/dashboard/accounts/new');
}
