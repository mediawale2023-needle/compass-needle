import { redirect } from 'next/navigation';

export default function ParliamentSyncLegacyRedirect() {
    redirect('/dashboard/system/parliament-sync');
}
