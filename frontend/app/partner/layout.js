'use client';

import { usePathname, useRouter } from 'next/navigation';
import { PartnerSessionProvider, usePartnerSession } from '@/lib/partnerSession';
import { buildPartnerTheme } from '@/lib/partnerTheme';
import PartnerShell from '@/components/partner/PartnerShell';
import './partner.css';

function PartnerFrame({ children }) {
    const { ready, token, partner, me, mustChangePassword, signOut } = usePartnerSession();
    const router = useRouter();
    const pathname = usePathname() || '';

    // White-label: the partner's colour drives a contrast-safe palette inside this subtree only.
    const { vars } = buildPartnerTheme(partner?.brand_color);
    const inApp = ready && token && partner && !mustChangePassword && pathname.startsWith('/partner/dashboard');

    return (
        <div className="pd" style={vars}>
            {inApp ? (
                <PartnerShell partner={partner} me={me} token={token}
                    onSignOut={() => { signOut(); router.push('/partner'); }}>
                    {children}
                </PartnerShell>
            ) : children}
        </div>
    );
}

export default function PartnerLayout({ children }) {
    return (
        <PartnerSessionProvider>
            <PartnerFrame>{children}</PartnerFrame>
        </PartnerSessionProvider>
    );
}
