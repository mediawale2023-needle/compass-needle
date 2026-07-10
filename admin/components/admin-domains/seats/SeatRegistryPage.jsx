'use client';
import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { apiGet } from '@/lib/api';

function seatBadge(seatType) {
    return seatType === 'mla'
        ? { className: 'badge badge-red', label: 'MLA' }
        : { className: 'badge badge-green', label: 'MP' };
}

function readinessOf(seat) {
    if (!seat.geography_ready) return { key: 'no_geography', label: 'No geography', className: 'badge badge-red badge-dot' };
    if (!seat.map_ready) return { key: 'no_map', label: 'Geography only', className: 'badge badge-amber badge-dot' };
    if ((seat.map_status || '') === 'live') return { key: 'live', label: 'Live', className: 'badge badge-green badge-dot' };
    return { key: 'ready', label: 'Map drafted', className: 'badge badge-slate badge-dot' };
}

export default function SeatRegistryPage() {
    const [seats, setSeats] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [search, setSearch] = useState('');
    const [typeFilter, setTypeFilter] = useState('all');

    useEffect(() => {
        apiGet('/api/admin/seats')
            .then((d) => setSeats(d.items || []))
            .catch((e) => setError(e.message || 'Failed to load seat registry'))
            .finally(() => setLoading(false));
    }, []);

    const filtered = useMemo(() => {
        const q = search.trim().toLowerCase();
        return seats.filter((s) => {
            if (typeFilter !== 'all' && (s.seat_type || 'mp') !== typeFilter) return false;
            if (!q) return true;
            return (
                (s.seat_name || '').toLowerCase().includes(q) ||
                (s.state || '').toLowerCase().includes(q) ||
                (s.tenants || []).some((t) => (t.name || '').toLowerCase().includes(q))
            );
        });
    }, [seats, search, typeFilter]);

    const counts = useMemo(() => ({
        total: seats.length,
        geographyReady: seats.filter((s) => s.geography_ready).length,
        withTenants: seats.filter((s) => (s.tenant_count || 0) > 0).length,
        needsAttention: seats.filter((s) => (s.tenant_count || 0) > 0 && !s.geography_ready).length,
    }), [seats]);

    return (
        <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: '1.5rem' }}>
                {[
                    { label: 'Seats', value: counts.total, accent: '#1a2e28' },
                    { label: 'Geography Ready', value: counts.geographyReady, accent: '#10b981' },
                    { label: 'With Accounts', value: counts.withTenants, accent: '#0ea5e9' },
                    { label: 'Accounts, No Geography', value: counts.needsAttention, accent: '#f43f5e' },
                ].map((c) => (
                    <div key={c.label} className="stat-card" style={{ borderLeft: `3px solid ${c.accent}` }}>
                        <div style={{ fontSize: '1.9rem', fontWeight: 800, color: c.accent, lineHeight: 1, letterSpacing: '-1px' }}>
                            {loading ? '…' : c.value}
                        </div>
                        <div style={{ color: '#6b7f76', fontSize: '0.72rem', fontWeight: 500, marginTop: 5, textTransform: 'uppercase', letterSpacing: '0.7px' }}>
                            {c.label}
                        </div>
                    </div>
                ))}
            </div>

            <div style={{ display: 'flex', gap: 10, marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
                <input
                    className="form-input"
                    style={{ maxWidth: 320 }}
                    placeholder="Search seat, state, or account…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                />
                {['all', 'mp', 'mla'].map((t) => (
                    <button
                        key={t}
                        className={typeFilter === t ? 'btn-primary' : 'btn-secondary'}
                        style={{ fontSize: '0.74rem', padding: '5px 12px' }}
                        onClick={() => setTypeFilter(t)}
                    >
                        {t === 'all' ? 'All seats' : t.toUpperCase()}
                    </button>
                ))}
                <div style={{ marginLeft: 'auto' }}>
                    <Link href="/dashboard/shared-geography/workspace" className="btn-secondary" style={{ textDecoration: 'none', fontSize: '0.74rem' }}>
                        Upload new seat geography
                    </Link>
                </div>
            </div>

            {error && <div className="toast toast-error" style={{ marginBottom: '1rem' }}>{error}</div>}

            {loading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {[...Array(6)].map((_, i) => <div key={i} className="skeleton" style={{ height: 48, borderRadius: 8 }} />)}
                </div>
            ) : filtered.length === 0 ? (
                <div className="glass-panel">
                    <div className="empty-state">
                        <div className="empty-state-title">No seats found</div>
                        <div className="empty-state-desc">Seats appear here once an account is created for a constituency or seat geography is uploaded.</div>
                    </div>
                </div>
            ) : (
                <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Seat</th>
                                <th>Accounts</th>
                                <th>Geography</th>
                                <th style={{ textAlign: 'right' }}>Corrections</th>
                                <th>Map</th>
                                <th>Readiness</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((s) => {
                                const badge = seatBadge(s.seat_type);
                                const readiness = readinessOf(s);
                                const corrections = (s.manual_correction_count || 0) + (s.legacy_correction_count || 0);
                                return (
                                    <tr key={s.seat_key}>
                                        <td style={{ fontWeight: 600 }}>
                                            <Link
                                                href={`/dashboard/seats/${encodeURIComponent(s.seat_key)}`}
                                                style={{ color: '#1a2e28', textDecoration: 'none' }}
                                            >
                                                {s.seat_name}
                                            </Link>
                                            <div style={{ marginTop: 3, display: 'flex', gap: 6, alignItems: 'center' }}>
                                                <span className={badge.className} style={{ fontSize: '0.62rem' }}>{badge.label}</span>
                                                {s.state ? <span style={{ fontSize: '0.7rem', color: '#94a3a0' }}>{s.state}</span> : null}
                                            </div>
                                        </td>
                                        <td style={{ color: '#6b7f76', fontSize: '0.8rem' }}>
                                            {(s.tenants || []).length === 0 ? '—' : (
                                                <>
                                                    {(s.tenants || []).slice(0, 2).map((t) => (
                                                        <div key={t.tenant_id}>
                                                            <Link href={`/dashboard/mps/${t.tenant_id}`} style={{ color: '#6b7f76' }}>
                                                                {t.name || `Tenant #${t.tenant_id}`}
                                                            </Link>
                                                        </div>
                                                    ))}
                                                    {(s.tenants || []).length > 2 && (
                                                        <div style={{ fontSize: '0.7rem', color: '#94a3a0' }}>+{s.tenants.length - 2} more</div>
                                                    )}
                                                </>
                                            )}
                                        </td>
                                        <td style={{ color: '#6b7f76', fontSize: '0.8rem' }}>
                                            {s.geography_ready
                                                ? `${s.assembly_count} assembl${s.assembly_count === 1 ? 'y' : 'ies'} · ${s.locality_count} localities`
                                                : <span style={{ color: '#9a3412' }}>Not uploaded</span>}
                                        </td>
                                        <td style={{ textAlign: 'right', fontWeight: 700, color: '#1a2e28' }}>
                                            {corrections}
                                            {s.legacy_correction_count > 0 && (
                                                <div style={{ marginTop: 2, fontSize: '0.66rem', color: '#94a3a0', fontWeight: 500 }}>
                                                    {s.legacy_correction_count} legacy
                                                </div>
                                            )}
                                        </td>
                                        <td style={{ color: '#6b7f76', fontSize: '0.8rem' }}>
                                            {s.map_ready ? (s.map_status || 'draft') : '—'}
                                            {s.boundary_ready && (
                                                <div style={{ fontSize: '0.66rem', color: '#94a3a0' }}>real boundary</div>
                                            )}
                                        </td>
                                        <td><span className={readiness.className}>{readiness.label}</span></td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </>
    );
}
