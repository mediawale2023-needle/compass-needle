import { redirect } from 'next/navigation';

export default function IntelligenceLegacyRedirect() {
    redirect('/dashboard/cases-intelligence/explorer');
}
