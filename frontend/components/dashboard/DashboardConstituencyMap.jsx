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

function collectGeoJsonRings(geojson) {
    const collection = geojson?.type === 'FeatureCollection'
        ? geojson.features || []
        : geojson?.type === 'Feature'
            ? [geojson]
            : [];
    const rings = [];
    collection.forEach((feature) => {
        const geometry = feature?.geometry || {};
        if (geometry.type === 'Polygon') {
            (geometry.coordinates || []).forEach((ring) => rings.push(ring));
        } else if (geometry.type === 'MultiPolygon') {
            (geometry.coordinates || []).forEach((polygon) => {
                (polygon || []).forEach((ring) => rings.push(ring));
            });
        }
    });
    return rings;
}

function deriveGeoJsonAspectRatio(geojson) {
    const rings = collectGeoJsonRings(geojson);
    const points = rings.flat();
    if (!points.length) return '100 / 72';

    const xs = points.map((point) => Number(point?.[0]) || 0);
    const ys = points.map((point) => Number(point?.[1]) || 0);
    const width = Math.max(Math.max(...xs) - Math.min(...xs), 1);
    const height = Math.max(Math.max(...ys) - Math.min(...ys), 1);
    const scaledHeight = Math.max(44, Math.min(120, Math.round(100 * (height / width))));
    return `100 / ${scaledHeight}`;
}

function buildGeoJsonProjection(geojson) {
    const rings = collectGeoJsonRings(geojson);
    const points = rings.flat();
    if (!points.length) return null;

    const xs = points.map((point) => Number(point?.[0]) || 0);
    const ys = points.map((point) => Number(point?.[1]) || 0);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const width = Math.max(maxX - minX, 1);
    const height = Math.max(maxY - minY, 1);
    const padding = 6;
    const usableWidth = 100 - padding * 2;
    const usableHeight = 72 - padding * 2;
    const scale = Math.min(usableWidth / width, usableHeight / height);
    const offsetX = (100 - width * scale) / 2;
    const offsetY = (72 - height * scale) / 2;

    const projectPoint = (point) => {
        const x = offsetX + (Number(point?.[0]) - minX) * scale;
        const y = 72 - (offsetY + (Number(point?.[1]) - minY) * scale);
        return `${x.toFixed(2)} ${y.toFixed(2)}`;
    };

    return { rings, projectPoint };
}

function buildPathData(rings, projectPoint) {
    return rings
        .map((ring) => {
            if (!Array.isArray(ring) || ring.length < 3) return '';
            const [first, ...rest] = ring;
            return `M ${projectPoint(first)} ${rest.map((point) => `L ${projectPoint(point)}`).join(' ')} Z`;
        })
        .filter(Boolean)
        .join(' ');
}

function GeoJsonBoundary({ geojson, assemblyGeojson = null }) {
    const projection = buildGeoJsonProjection(geojson);
    if (!projection) return null;
    const { rings, projectPoint } = projection;

    const pathData = buildPathData(rings, projectPoint);
    if (!pathData) return null;
    const assemblyPathData = assemblyGeojson ? buildPathData(collectGeoJsonRings(assemblyGeojson), projectPoint) : '';

    return (
        <svg viewBox="0 0 100 72" width="100%" height="100%" style={{ display: 'block' }}>
            <defs>
                <linearGradient id="constituencyGeoFill" x1="0%" x2="100%" y1="0%" y2="100%">
                    <stop offset="0%" stopColor="#F6F0E1" />
                    <stop offset="100%" stopColor="#ECE3CE" />
                </linearGradient>
            </defs>
            <path d={pathData} fill="url(#constituencyGeoFill)" stroke={P.hairStrong} strokeWidth="0.7" />
            {assemblyPathData ? (
                <path
                    d={assemblyPathData}
                    fill="none"
                    stroke="#A89E87"
                    strokeWidth="0.45"
                    strokeOpacity="0.85"
                    vectorEffect="non-scaling-stroke"
                />
            ) : null}
        </svg>
    );
}

function normalizeApiManifest(manifest) {
    if (!manifest || typeof manifest !== 'object') return null;
    const inlineSvg = manifest.asset?.inline_svg || null;
    const assetPath = manifest.asset?.path
        || (inlineSvg ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(inlineSvg)}` : null);
    const geojson = manifest.asset?.geojson || null;
    return {
        seatKey: manifest.seat_key,
        seatType: manifest.seat_type,
        seatName: manifest.seat_name,
        state: manifest.state || null,
        assetPath,
        geojson,
        assemblyGeojson: manifest.asset?.assembly_geojson || null,
        assetType: manifest.asset?.type || 'svg',
        aspectRatio: manifest.asset?.aspect_ratio || (geojson ? deriveGeoJsonAspectRatio(geojson) : '1 / 1'),
        features: manifest.features || [],
        fallbackAnchors: manifest.fallback_anchors || [],
        registryStatus: manifest.status || 'draft',
        version: manifest.version || 1,
        generated: Boolean(manifest.asset?.generated),
    };
}

function toAnchorPercents(anchor = {}) {
    const rawX = Number(anchor?.x);
    const rawY = Number(anchor?.y);
    const x = Number.isFinite(rawX) ? rawX : 50;
    const y = Number.isFinite(rawY) ? rawY : 36;
    return {
        left: `${x}%`,
        top: `${(y / 72) * 100}%`,
    };
}

export default function DashboardConstituencyMap({ summary, user, mapManifest = null }) {
    const redZones = (summary?.red_zones || []).map((zone) => ({
        area: zone.area || zone.name || '',
        count: zone.count ?? zone.cnt ?? 0,
    })).filter((zone) => zone.area);
    const categories = summary?.category_breakdown || {};
    const topCategories = Object.entries(categories).sort((a, b) => b[1] - a[1]).slice(0, 3);
    const maxLoad = Math.max(...redZones.map((zone) => zone.count || 0), 1);
    const mapConfig = normalizeApiManifest(mapManifest) || getConstituencyMapConfig({ constituency: user?.constituency, seatType: user?.seat_type });
    const hotspots = mapConfig
        ? redZones.slice(0, 8).map((zone, index) => ({ ...zone, ...resolveConstituencyHotspot(mapConfig, zone.area, index) }))
        : [];

    return (
        <section
            className="min-w-0"
            style={{ background: P.surface, border: `1px solid ${P.hair}`, padding: 16, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}
        >
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
                    <div style={{ position: 'relative', width: '100%', aspectRatio: mapConfig.aspectRatio, minHeight: 140, maxHeight: '100%' }}>
                        {mapConfig.assetType === 'geojson' && mapConfig.geojson ? (
                            <GeoJsonBoundary geojson={mapConfig.geojson} assemblyGeojson={mapConfig.assemblyGeojson} />
                        ) : (
                            <img
                                src={mapConfig.assetPath}
                                alt={`${user?.constituency || 'Constituency'} outline`}
                                style={{ width: '100%', height: '100%', display: 'block' }}
                            />
                        )}
                        {hotspots.map((zone, index) => {
                            const radius = 16 + (zone.count ? (zone.count / maxLoad) * 14 : 8);
                            const anchorStyle = toAnchorPercents(zone);
                            return (
                                <Link
                                    key={`${zone.area}-${index}`}
                                    href={`/dashboard/sansadx?location=${encodeURIComponent(zone.area)}`}
                                    title={`${zone.area}: ${zone.count} cases`}
                                    style={{
                                        position: 'absolute',
                                        left: anchorStyle.left,
                                        top: anchorStyle.top,
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
                            {mapConfig.generated ? 'Generated seat map' : (mapConfig.assetType === 'geojson' ? 'Real GeoJSON boundary' : 'Real seat outline')}
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
