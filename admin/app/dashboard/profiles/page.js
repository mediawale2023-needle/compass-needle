import { redirect } from 'next/navigation';

export default function ProfilesLegacyRedirect() {
    redirect('/dashboard/accounts/registry');
}
