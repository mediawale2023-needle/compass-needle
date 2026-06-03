import { redirect } from 'next/navigation';

export default function HealthLegacyRedirect() {
    redirect('/dashboard/system/health');
}
