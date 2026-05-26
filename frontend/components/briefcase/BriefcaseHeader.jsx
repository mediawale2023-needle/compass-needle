'use client';

import Link from 'next/link';
import { briefcaseFonts, briefcasePalette as P, BriefcaseIcon } from '@/components/briefcase/briefcase-shared';

const { serif: SERIF, mono: MONO } = briefcaseFonts;

export default function BriefcaseHeader({ searchInput, onSearchInputChange, subtitle, user }) {
    const initials = user?.display_name
        ? user.display_name.split(' ').map((word) => word[0]).slice(0, 2).join('').toUpperCase()
        : 'MP';

    return (
        <>
            <header
                className="md:hidden"
                style={{
                    background: P.paper,
                    borderBottom: `1px solid ${P.hair}`,
                    padding: '14px 14px 12px',
                }}
            >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ minWidth: 0 }}>
                        <div
                            style={{
                                fontFamily: SERIF,
                                fontWeight: 600,
                                fontSize: 24,
                                color: P.ink,
                                letterSpacing: '-0.01em',
                                lineHeight: 1.02,
                            }}
                        >
                            Briefcase
                        </div>
                        <div style={{ fontSize: 11.5, color: P.ink2, marginTop: 4, lineHeight: 1.35 }}>
                            {subtitle}
                        </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <button
                            style={{
                                width: 34,
                                height: 34,
                                border: `1px solid ${P.hair}`,
                                background: P.surface,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                position: 'relative',
                            }}
                        >
                            <BriefcaseIcon name="bell" size={14} color={P.ink2} />
                            <span
                                style={{
                                    position: 'absolute',
                                    top: -3,
                                    right: -3,
                                    minWidth: 15,
                                    height: 15,
                                    padding: '0 4px',
                                    fontSize: 8.5,
                                    background: P.saffron,
                                    color: '#fff',
                                    fontFamily: MONO,
                                    fontWeight: 700,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                }}
                            >
                                28
                            </span>
                        </button>
                        <div
                            style={{
                                width: 34,
                                height: 34,
                                background: P.green,
                                color: '#F5EFE0',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontFamily: SERIF,
                                fontWeight: 600,
                                fontSize: 13,
                            }}
                        >
                            {initials}
                        </div>
                    </div>
                </div>

                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '9px 11px',
                        marginTop: 12,
                        background: P.surface,
                        border: `1px solid ${P.hair}`,
                    }}
                >
                    <BriefcaseIcon name="search" size={14} color={P.ink3} />
                    <input
                        placeholder="Search citizen, ref, message…"
                        value={searchInput}
                        onChange={(event) => onSearchInputChange(event.target.value)}
                        style={{
                            flex: 1,
                            border: 'none',
                            background: 'transparent',
                            outline: 'none',
                            fontSize: 12.5,
                            color: P.ink,
                            fontFamily: 'inherit',
                            minWidth: 0,
                        }}
                    />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10 }}>
                    <Link
                        href="/dashboard/sansadai"
                        style={{
                            flex: 1,
                            padding: '9px 12px',
                            background: P.green,
                            color: '#F5EFE0',
                            fontSize: 11,
                            letterSpacing: '0.08em',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: 6,
                            fontFamily: 'inherit',
                            textDecoration: 'none',
                        }}
                    >
                        <BriefcaseIcon name="sparkle" size={12} color="#F5EFE0" /> Sansad AI
                    </Link>
                    <div
                        style={{
                            padding: '8px 10px',
                            border: `1px solid ${P.hair}`,
                            background: P.surfaceWarm,
                            fontSize: 10.5,
                            color: P.ink3,
                        }}
                    >
                        {user?.role === 'mp' ? 'MP' : user?.role === 'admin' ? 'Admin' : 'Staff'}
                    </div>
                </div>
            </header>

            <header
                className="hidden md:grid"
                style={{
                    background: P.paper,
                    borderBottom: `1px solid ${P.hair}`,
                    gridTemplateColumns: 'auto 1fr auto auto auto',
                    alignItems: 'center',
                    gap: 14,
                    padding: '12px 22px',
                }}
            >
                <div>
                    <div
                        style={{
                            fontFamily: SERIF,
                            fontWeight: 600,
                            fontSize: 22,
                            color: P.ink,
                            letterSpacing: '-0.01em',
                            lineHeight: 1.05,
                        }}
                    >
                        Briefcase
                    </div>
                    <div style={{ fontSize: 12, color: P.ink2, marginTop: 3 }}>
                        {subtitle}
                    </div>
                </div>

                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '8px 12px',
                        width: 460,
                        justifySelf: 'center',
                        background: P.surface,
                        border: `1px solid ${P.hair}`,
                    }}
                >
                    <BriefcaseIcon name="search" size={14} color={P.ink3} />
                    <input
                        placeholder="Search citizen, ref, message, location…"
                        value={searchInput}
                        onChange={(event) => onSearchInputChange(event.target.value)}
                        style={{
                            flex: 1,
                            border: 'none',
                            background: 'transparent',
                            outline: 'none',
                            fontSize: 12.5,
                            color: P.ink,
                            fontFamily: 'inherit',
                        }}
                    />
                    <span
                        style={{
                            fontFamily: MONO,
                            fontSize: 10,
                            color: P.ink3,
                            border: `1px solid ${P.hair}`,
                            padding: '1px 5px',
                        }}
                    >
                        ⌘K
                    </span>
                </div>

                <Link
                    href="/dashboard/sansadai"
                    style={{
                        padding: '7px 12px',
                        background: P.green,
                        color: '#F5EFE0',
                        border: 'none',
                        fontSize: 11,
                        letterSpacing: '0.08em',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        fontFamily: 'inherit',
                        textDecoration: 'none',
                    }}
                >
                    <BriefcaseIcon name="sparkle" size={12} color="#F5EFE0" /> Sansad AI
                </Link>

                <button
                    style={{
                        width: 36,
                        height: 36,
                        border: `1px solid ${P.hair}`,
                        background: P.surface,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        position: 'relative',
                    }}
                >
                    <BriefcaseIcon name="bell" size={15} color={P.ink2} />
                    <span
                        style={{
                            position: 'absolute',
                            top: -4,
                            right: -4,
                            minWidth: 16,
                            height: 16,
                            padding: '0 4px',
                            fontSize: 9,
                            background: P.saffron,
                            color: '#fff',
                            fontFamily: MONO,
                            fontWeight: 700,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                        }}
                    >
                        28
                    </span>
                </button>

                <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                    <div
                        style={{
                            width: 34,
                            height: 34,
                            background: P.green,
                            color: '#F5EFE0',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontFamily: SERIF,
                            fontWeight: 600,
                            fontSize: 13,
                        }}
                    >
                        {initials}
                    </div>
                    <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: P.ink, lineHeight: 1.1 }}>
                            {user?.display_name || 'Member'}
                        </div>
                        <div style={{ fontSize: 10, color: P.ink3 }}>
                            {user?.role === 'mp' ? 'MP' : user?.role === 'admin' ? 'Admin' : 'Staff'}
                        </div>
                    </div>
                </div>
            </header>
        </>
    );
}
