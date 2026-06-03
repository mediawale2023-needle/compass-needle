import { redirect } from 'next/navigation';

export default function RulesLegacyRedirect() {
    redirect('/dashboard/shared-geography/rules');
}
