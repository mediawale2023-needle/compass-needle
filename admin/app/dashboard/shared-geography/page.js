import { redirect } from 'next/navigation';

// Shared Geography is now part of the Seats domain: the seat registry links
// into per-seat geography, corrections, and the upload workspace. This
// landing stays as a compatibility redirect only.
export default function SharedGeographyPage() {
    redirect('/dashboard/seats');
}
