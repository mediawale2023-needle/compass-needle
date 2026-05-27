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
                <h1
                    style={{
                        margin: 0,
                        fontFamily: SERIF,
                        fontWeight: 600,
                        fontSize: 22,
                        color: P.ink,
                        letterSpacing: '-0.01em',
                        lineHeight: 1.05,
                    }}
                >
                    Briefcase
                </h1>
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

        <header
            className="md:hidden"
            style={{
                background: P.paper,
                borderBottom: `1px solid ${P.hair}`,
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
                padding: '10px 16px',
            }}
        >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                <div style={{ minWidth: 0 }}>
                    <div
                        style={{
                            fontFamily: SERIF,
                            fontWeight: 600,
                            fontSize: 19,
                            color: P.ink,
                            letterSpacing: '-0.01em',
                            lineHeight: 1.05,
                        }}
                    >
                        Briefcase
                    </div>
                    <div
                        style={{
                            fontSize: 11,
                            color: P.ink2,
                            marginTop: 2,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {subtitle}
                    </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                    <Link
                        href="/dashboard/sansadai"
                        aria-label="Sansad AI"
                        style={{
                            width: 34,
                            height: 34,
                            background: P.green,
                            color: '#F5EFE0',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            textDecoration: 'none',
                        }}
                    >
                        <BriefcaseIcon name="sparkle" size={15} color="#F5EFE0" />
                    </Link>
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
                    padding: '8px 12px',
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
                        minWidth: 0,
                        border: 'none',
                        background: 'transparent',
                        outline: 'none',
                        fontSize: 13,
                        color: P.ink,
                        fontFamily: 'inherit',
                    }}
                />
            </div>
        </header>
        </>
    );
}
