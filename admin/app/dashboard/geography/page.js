import { redirect } from 'next/navigation';

export default function GeographyLegacyRedirect() {
    redirect('/dashboard/shared-geography/workspace');
}
