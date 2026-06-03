import { redirect } from 'next/navigation';

export default function AnnouncementsLegacyRedirect() {
    redirect('/dashboard/system/announcements');
}
