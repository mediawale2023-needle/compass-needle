'use client';

import Link from 'next/link';
import { dashboardFonts, dashboardPalette as P } from '@/lib/dashboard-theme';

const { serif: SERIF } = dashboardFonts;

export default function DashboardEmptyState({ canUseSansadAI }) {
    const actions = [
        { label: 'Upload a Letter', href: '/dashboard/letterbox' },
        { label: 'Log a Case', href: '/dashboard/sansadx' },
        ...(canUseSansadAI ? [{ label: 'Open Sansad AI', href: '/dashboard/sansadai' }] : []),
        { label: 'Find a Scheme', href: '/dashboard/sansadai?tab=schemes' },
    ];

    return (
        <div
            style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '64px 24px',
                background: P.surface,
                border: `1px solid ${P.hair}`,
                textAlign: 'center',
                gap: 16,
            }}
        >
            <div
                style={{
                    width: 64,
                    height: 64,
                    background: P.greenTint,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                }}
            >
                <span style={{ fontFamily: SERIF, fontSize: 32, color: P.green }}>क</span>
            </div>
            <div>
                <h2 style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 22, color: P.ink, marginBottom: 8 }}>
                    Welcome to Compass Needle
                </h2>
                <p style={{ fontSize: 14, color: P.ink2, maxWidth: 420, lineHeight: 1.6 }}>
                    Your constituency operations console is ready. Start by uploading a letter, logging a new case, or preparing your first response draft.
                </p>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center' }}>
                {actions.map((action) => (
                    <Link
                        key={action.href}
                        href={action.href}
                        style={{
                            padding: '8px 16px',
                            border: `1px solid ${P.hair}`,
                            background: P.paper,
                            color: P.ink,
                            fontSize: 12.5,
                            fontWeight: 500,
                            textDecoration: 'none',
                            transition: 'opacity 0.15s',
                        }}
                    >
                        {action.label}
                    </Link>
                ))}
            </div>
        </div>
    );
}
