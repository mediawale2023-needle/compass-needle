'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { canAccessSansadAI, getAccountLabel } from '@/lib/account';

// Shared Overview / Case Detail visual system.
const C = {
    bg: '#F3EEE2',
    surface: '#FFFEFB',
    border: '#E4DECB',
    borderStrong: '#C9BFA9',
    ink: '#211F19',
    muted: '#6C6858',
    faint: '#8A8270',
    green: '#2B6E4C',
    greenDeep: '#245F45',
};
const SANS = '"Public Sans", "Noto Sans Devanagari", system-ui, sans-serif';
const SERIF = '"Source Serif 4", Georgia, serif';
const MONO = '"IBM Plex Mono", ui-monospace, SFMono-Regular, monospace';

// Local desktop/mobile switch. The previous mobile header set an inline
// `display: flex` alongside `className="md:hidden"`; the inline style outranks
// the responsive utility, so both the desktop and mobile headers rendered at
// desktop widths. Selecting one header in JS keeps that class of mistake out.
function useIsDesktop() {
    const [isDesktop, setIsDesktop] = useState(true);
    useEffect(() => {
        if (typeof window === 'undefined' || !window.matchMedia) return undefined;
        const mq = window.matchMedia('(min-width: 768px)');
        const update = () => setIsDesktop(mq.matches);
        update();
        mq.addEventListener('change', update);
        return () => mq.removeEventListener('change', update);
    }, []);
    return isDesktop;
}

function SearchInput({ value, onChange, placeholder }) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 11px', background: C.surface, border: `1px solid ${C.borderStrong}`, minWidth: 0 }}>
            <span aria-hidden="true" style={{ color: C.faint, fontSize: 13 }}>⌕</span>
            <input
                placeholder={placeholder}
                value={value}
                onChange={(event) => onChange(event.target.value)}
                style={{ flex: 1, minWidth: 0, border: 'none', background: 'transparent', outline: 'none', fontSize: 12.5, color: C.ink, fontFamily: SANS }}
            />
        </div>
    );
}

export default function BriefcaseHeader({ searchInput, onSearchInputChange, subtitle, user }) {
    const isDesktop = useIsDesktop();
    const initials = user?.display_name
        ? user.display_name.split(' ').map((word) => word[0]).slice(0, 2).join('').toUpperCase()
        : 'CN';

    const avatar = (
        <div style={{ width: 32, height: 32, background: C.green, color: '#F3EEE2', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: SERIF, fontWeight: 600, fontSize: 12.5, flexShrink: 0 }}>
            {initials}
        </div>
    );

    if (isDesktop) {
        return (
            <header
                style={{
                    background: C.bg,
                    borderBottom: `1px solid ${C.border}`,
                    display: 'grid',
                    gridTemplateColumns: 'auto 1fr auto auto',
                    alignItems: 'center',
                    gap: 14,
                    padding: '11px 22px',
                }}
            >
                <div>
                    <h1 style={{ margin: 0, fontFamily: SERIF, fontWeight: 700, fontSize: 21, color: C.ink, letterSpacing: '-0.015em', lineHeight: 1.05 }}>
                        Briefcase
                    </h1>
                    <div style={{ fontSize: 11.5, color: C.muted, marginTop: 3 }}>{subtitle}</div>
                </div>

                <div style={{ width: 440, justifySelf: 'center' }}>
                    <SearchInput value={searchInput} onChange={onSearchInputChange} placeholder="Search citizen, ref, message, location…" />
                </div>

                {canAccessSansadAI(user) ? (
                    <Link
                        href="/dashboard/sansadai"
                        style={{ padding: '7px 12px', background: C.green, color: '#F3EEE2', border: 'none', fontSize: 10.5, letterSpacing: '0.08em', fontWeight: 600, textTransform: 'uppercase', display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: MONO, textDecoration: 'none' }}
                    >
                        Sansad AI
                    </Link>
                ) : <span />}

                <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                    {avatar}
                    <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: C.ink, lineHeight: 1.1 }}>{user?.display_name || 'Workspace User'}</div>
                        <div style={{ fontSize: 10, color: C.faint, fontFamily: MONO }}>{getAccountLabel(user)}</div>
                    </div>
                </div>
            </header>
        );
    }

    return (
        <header style={{ background: C.bg, borderBottom: `1px solid ${C.border}` }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '10px 14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                    <div style={{ minWidth: 0 }}>
                        <div style={{ fontFamily: SERIF, fontWeight: 700, fontSize: 18, color: C.ink, letterSpacing: '-0.015em', lineHeight: 1.05 }}>
                            Briefcase
                        </div>
                        <div style={{ fontSize: 11, color: C.muted, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {subtitle}
                        </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                        {canAccessSansadAI(user) && (
                            <Link href="/dashboard/sansadai" aria-label="Sansad AI" style={{ width: 32, height: 32, background: C.green, color: '#F3EEE2', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontFamily: MONO, fontSize: 11, fontWeight: 700, textDecoration: 'none' }}>
                                AI
                            </Link>
                        )}
                        {avatar}
                    </div>
                </div>
                <SearchInput value={searchInput} onChange={onSearchInputChange} placeholder="Search citizen, ref, message…" />
            </div>
        </header>
    );
}
