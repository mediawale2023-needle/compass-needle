'use client';

import { PartnerSessionProvider, usePartnerSession } from '@/lib/partnerSession';
import { hexToHslTriplet } from '@/lib/partnerFormat';
import { Button } from '@/components/ui/button';
import { LogOut } from 'lucide-react';
import { useRouter } from 'next/navigation';

function PartnerShell({ children }) {
    const { ready, token, partner, signOut } = usePartnerSession();
    const router = useRouter();

    // White-label: the partner's own colour drives the primary token inside this subtree only.
    const hsl = hexToHslTriplet(partner?.brand_color);
    const themeStyle = hsl ? { '--primary': hsl, '--ring': hsl } : undefined;
    const showHeader = ready && token && partner;

    return (
        <div className="min-h-screen bg-background text-foreground" style={themeStyle}>
            {showHeader && (
                <header className="border-b bg-card">
                    <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
                        <div className="flex min-w-0 items-center gap-3">
                            {partner.brand_logo_url ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img src={partner.brand_logo_url} alt="" className="h-8 max-w-[140px] object-contain" />
                            ) : null}
                            <span className="truncate font-serif text-lg font-semibold">{partner.brand_name}</span>
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                                signOut();
                                router.push('/partner');
                            }}
                        >
                            <LogOut aria-hidden="true" /> Sign out
                        </Button>
                    </div>
                </header>
            )}
            <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">{children}</main>
            {showHeader && partner.show_powered_by && (
                <footer className="mx-auto max-w-6xl px-4 pb-8 text-xs text-muted-foreground sm:px-6">
                    Intelligence by Compass Needle
                </footer>
            )}
        </div>
    );
}

export default function PartnerLayout({ children }) {
    return (
        <PartnerSessionProvider>
            <PartnerShell>{children}</PartnerShell>
        </PartnerSessionProvider>
    );
}
