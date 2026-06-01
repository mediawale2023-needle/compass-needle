'use client';

import Link from 'next/link';
import { dashboardFonts, dashboardPalette as P } from '@/lib/dashboard-theme';
import { getConstituencyMapConfig, resolveConstituencyHotspot } from '@/lib/constituency-map-data';

const { serif: SERIF, mono: MONO } = dashboardFonts;

function heat(load, maxLoad) {
    const ratio = (load || 0) / maxLoad;
    if (ratio > 0.75) return '#8B2E1F';
    if (ratio > 0.55) return P.saffron;
    if (ratio > 0.35) return '#D89E55';
    if (ratio > 0.18) return '#7DA08E';
    return P.greenTint;
}

function LegacyFallbackMap({ redZones, maxLoad }) {
    const width = 340;
    const height = 200;
    const outline = 'M 35 110 C 25 70, 65 35, 110 32 C 155 28, 200 50, 235 38 C 280 28, 330 55, 345 100 C 360 145, 330 195, 280 205 C 230 215, 170 200, 115 210 C 60 220, 25 175, 35 110 Z';
    const positions = [[70, 80], [120, 60], [170, 95], [225, 70], [280, 95], [320, 130], [85, 145], [135, 130], [195, 150], [245, 130], [290, 165], [200, 195]];
    const wardDots = redZones.length > 0
        ? redZones.slice(0, 12).map((zone, index) => ({ ...zone, pos: positions[index] || [170, 110] }))
        : positions.slice(0, 6).map((pos, index) => ({ pos, area: `Zone ${index + 1}`, count: 0 }));

    return (
        <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="100%" style={{ display: 'block' }}>
            <path d={outline} fill={P.paperDeep} stroke={P.hairStrong} strokeWidth="1" strokeDasharray="2 3" />
            <path d="M 40 195 C 90 175, 150 180, 200 170 S 320 160, 350 155" stroke={P.blue} strokeWidth="2" fill="none" opacity="0.4" />
            {wardDots.map((ward, index) => {
                const [cx, cy] = ward.pos;
                const radius = 8 + (ward.count ? (ward.count / maxLoad) * 12 : 6);
                return (
                    <g key={`${ward.area || 'zone'}-${index}`}>
                        <circle cx={cx} cy={cy} r={radius} fill={heat(ward.count, maxLoad)} fillOpacity="0.85" stroke="#fff" strokeWidth="1.2" />
                        <text
                            x={cx}
                            y={cy + 3}
                            fontFamily={SERIF}
                            fontSize="9"
                            fontWeight="600"
                            fill={ward.count > maxLoad * 0.35 ? '#F5EFE0' : P.ink}
                            textAnchor="middle"
                        >
                            {index + 1}
                        </text>
                    </g>
                );
            })}
        </svg>
    );
}

export default function DashboardConstituencyMap({ summary, user }) {
    const redZones = (summary?.red_zones || []).map((zone) => ({
        area: zone.area || zone.name || '',
        count: zone.count ?? zone.cnt ?? 0,
    })).filter((zone) => zone.area);
    const categories = summary?.category_breakdown || {};
    const topCategories = Object.entries(categories).sort((a, b) => b[1] - a[1]).slice(0, 3);
    const maxLoad = Math.max(...redZones.map((zone) => zone.count || 0), 1);
    const mapConfig = getConstituencyMapConfig({ constituency: user?.constituency, seatType: user?.seat_type });
    const hotspots = mapConfig
        ? redZones.slice(0, 8).map((zone, index) => ({ ...zone, ...resolveConstituencyHotspot(mapConfig, zone.area, index) }))
        : [];

    return (
        <section className="min-w-0" style={{ background: P.surface, border: `1px solid ${P.hair}`, padding: 16, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 8 }}>
                <div>
                    <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 15, color: P.ink }}>
                        Constituency map · {user?.constituency || '—'}
                    </div>
                    <div style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '0.12em', color: P.ink3, marginTop: 2, textTransform: 'uppercase' }}>
                        Grievance load · live
                    </div>
                </div>
                <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
                    {[P.greenTint, '#7DA08E', '#D89E55', P.saffron, '#8B2E1F'].map((color, index) => (
                        <span key={index} style={{ width: 12, height: 8, background: color, display: 'block' }} />
                    ))}
                </div>
            </div>

            <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
                {mapConfig ? (
                    <div style={{ position: 'relative', width: '100%', aspectRatio: mapConfig.aspectRatio, minHeight: 180 }}>
                        <img
                            src={mapConfig.assetPath}
                            alt={`${user?.constituency || 'Constituency'} outline`}
                            style={{ width: '100%', height: '100%', display: 'block' }}
                        />
                        {hotspots.map((zone, index) => {
                            const radius = 16 + (zone.count ? (zone.count / maxLoad) * 14 : 8);
                            return (
                                <Link
                                    key={`${zone.area}-${index}`}
                                    href={`/dashboard/sansadx?location=${encodeURIComponent(zone.area)}`}
                                    title={`${zone.area}: ${zone.count} cases`}
                                    style={{
                                        position: 'absolute',
                                        left: `${zone.x}%`,
                                        top: `${zone.y}%`,
                                        width: radius,
                                        height: radius,
                                        marginLeft: -(radius / 2),
                                        marginTop: -(radius / 2),
                                        borderRadius: '999px',
                                        background: heat(zone.count, maxLoad),
                                        border: '2px solid rgba(255,255,255,0.96)',
                                        boxShadow: '0 6px 16px rgba(32, 25, 18, 0.22)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        textDecoration: 'none',
                                        color: zone.count > maxLoad * 0.35 ? '#F7F1E4' : P.ink,
                                        fontFamily: SERIF,
                                        fontWeight: 600,
                                        fontSize: 10,
                                    }}
                                >
                                    {zone.count}
                                </Link>
                            );
                        })}
                        <div
                            style={{
                                position: 'absolute',
                                right: 8,
                                bottom: 8,
                                padding: '5px 7px',
                                background: 'rgba(250, 246, 237, 0.92)',
                                border: `1px solid ${P.hair}`,
                                fontFamily: MONO,
                                fontSize: 9,
                                letterSpacing: '0.08em',
                                textTransform: 'uppercase',
                                color: P.ink3,
                            }}
                        >
                            Real seat outline
                        </div>
                    </div>
                ) : (
                    <LegacyFallbackMap redZones={redZones} maxLoad={maxLoad} />
                )}
            </div>

            {hotspots.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2.5">
                    {hotspots.map((zone) => (
                        <Link
                            key={zone.area}
                            href={`/dashboard/sansadx?location=${encodeURIComponent(zone.area)}`}
                            style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 6,
                                padding: '5px 7px',
                                background: P.paper,
                                border: `1px solid ${P.hair}`,
                                color: P.ink,
                                textDecoration: 'none',
                            }}
                        >
                            <span style={{ width: 9, height: 9, borderRadius: '999px', background: heat(zone.count, maxLoad), display: 'inline-block' }} />
                            <span style={{ fontFamily: MONO, fontSize: 9, color: P.ink3, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                                {zone.area}
                            </span>
                            <span style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 12 }}>
                                {zone.count}
                            </span>
                        </Link>
                    ))}
                </div>
            )}

            {topCategories.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 mt-2.5">
                    {topCategories.map(([category, count]) => (
                        <Link key={category} href={`/dashboard/sansadx?category=${encodeURIComponent(category)}`} style={{ textDecoration: 'none' }}>
                            <div style={{ padding: '6px 8px', background: P.paper, border: `1px solid ${P.hair}` }}>
                                <div style={{ fontFamily: MONO, fontSize: 9, color: P.ink3, letterSpacing: '0.08em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {category}
                                </div>
                                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                                    <span style={{ fontFamily: SERIF, fontSize: 16, fontWeight: 600, color: P.ink }}>{count}</span>
                                    <span style={{ fontSize: 9.5, color: P.ink3 }}>cases</span>
                                </div>
                            </div>
                        </Link>
                    ))}
                </div>
            )}
        </section>
    );
}
