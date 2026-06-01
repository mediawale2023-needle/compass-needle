'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { apiGet, apiPost } from '@/lib/api';

const CARD = {
    background: '#fff',
    border: '1px solid #e2ebe5',
    borderRadius: 14,
    boxShadow: '0 8px 24px rgba(16, 24, 20, 0.04)',
};

const INPUT = {
    width: '100%',
    border: '1px solid #d7e3dc',
    borderRadius: 10,
    padding: '10px 12px',
    fontSize: '0.92rem',
    color: '#1a2e28',
    background: '#fff',
    outline: 'none',
};

const LABEL = {
    display: 'block',
    fontSize: '0.76rem',
    fontWeight: 700,
    color: '#587166',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    marginBottom: 6,
};

const SMALL_BTN = {
    border: '1px solid #d7e3dc',
    background: '#fff',
    color: '#365247',
    borderRadius: 10,
    padding: '8px 12px',
    fontSize: '0.82rem',
    fontWeight: 600,
    cursor: 'pointer',
};

function blankSeat() {
    return {
        seat_key: '',
        seat_type: 'mla',
        seat_name: '',
        state: '',
        tenant_count: 0,
        tenants: [],
        assembly_count: 0,
        locality_count: 0,
        geography_ready: false,
        map_ready: false,
        map_status: null,
        map_source: null,
        generated: false,
        boundary_ready: false,
        boundary_type: null,
        boundary_source: null,
        manifest: null,
    };
}

function normalizeSeat(item) {
    if (!item) return blankSeat();
    return {
        ...blankSeat(),
        ...item,
        seat_key: item.seat_key || '',
        seat_type: item.seat_type || 'mla',
        seat_name: item.seat_name || '',
        state: item.state || '',
        tenants: item.tenants || [],
    };
}

function badgeStyle(kind) {
    if (kind === 'ready') return { background: '#eef9f4', color: '#006a4d', border: '1px solid #bfdfcd' };
    if (kind === 'warn') return { background: '#fff7e8', color: '#8b6f1a', border: '1px solid #ead7aa' };
    return { background: '#f7f7f7', color: '#6b7f76', border: '1px solid #dde6e1' };
}

export default function SeatMapsPage() {
    const [items, setItems] = useState([]);
    const [selectedKey, setSelectedKey] = useState('');
    const [draft, setDraft] = useState(blankSeat());
    const [loading, setLoading] = useState(true);
    const [working, setWorking] = useState(false);
    const [boundarySaving, setBoundarySaving] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [boundaryDraft, setBoundaryDraft] = useState({ asset_type: 'svg', asset_path: '', inline_svg: '', aspect_ratio: '100 / 72' });

    async function loadWorkflow(preferredKey = '') {
        setLoading(true);
        setError('');
        try {
            const response = await apiGet('/api/admin/seat-maps/workflow');
            const nextItems = response.items || [];
            setItems(nextItems);
            const targetKey = preferredKey || selectedKey || nextItems[0]?.seat_key || '';
            const target = nextItems.find((item) => item.seat_key === targetKey) || nextItems[0] || blankSeat();
            setSelectedKey(target.seat_key || '');
            setDraft(normalizeSeat(target));
            const manifestAsset = target.manifest?.asset || {};
            setBoundaryDraft({
                asset_type: target.boundary_type || manifestAsset.type || 'svg',
                asset_path: manifestAsset.path || '',
                inline_svg: manifestAsset.generated ? '' : (manifestAsset.inline_svg || ''),
                aspect_ratio: manifestAsset.aspect_ratio || '100 / 72',
            });
        } catch (err) {
            setError(err.message || 'Unable to load seat workflows.');
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        loadWorkflow();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const selectedSeat = useMemo(
        () => items.find((item) => item.seat_key === selectedKey) || null,
        [items, selectedKey]
    );

    function selectSeat(item) {
        setSelectedKey(item.seat_key || '');
        setDraft(normalizeSeat(item));
        const manifestAsset = item.manifest?.asset || {};
        setBoundaryDraft({
            asset_type: item.boundary_type || manifestAsset.type || 'svg',
            asset_path: manifestAsset.path || '',
            inline_svg: item.generated ? '' : (manifestAsset.inline_svg || ''),
            aspect_ratio: manifestAsset.aspect_ratio || '100 / 72',
        });
        setError('');
        setNotice('');
    }

    function startNewSeat() {
        setSelectedKey('');
        setDraft(blankSeat());
        setBoundaryDraft({ asset_type: 'svg', asset_path: '', inline_svg: '', aspect_ratio: '100 / 72' });
        setError('');
        setNotice('');
    }

    async function generateSeatMap() {
        const seatName = String(draft.seat_name || '').trim();
        if (!seatName) {
            setError('Seat name is required.');
            setNotice('');
            return;
        }
        setWorking(true);
        setError('');
        setNotice('');
        try {
            const response = await apiPost('/api/admin/seat-maps/generate', {
                seat_key: String(draft.seat_key || '').trim() || null,
                seat_type: String(draft.seat_type || 'mla').trim(),
                seat_name: seatName,
                state: String(draft.state || '').trim(),
                aliases: [seatName],
            });
            const manifest = response.manifest;
            await loadWorkflow(manifest.seat_key);
            setNotice(`${selectedSeat?.map_ready ? 'Regenerated' : 'Generated'} ${manifest.seat_key}`);
        } catch (err) {
            setError(err.message || 'Unable to generate seat map.');
        } finally {
            setWorking(false);
        }
    }

    async function saveBoundary() {
        const seatName = String(draft.seat_name || '').trim();
        if (!seatName) {
            setError('Seat name is required before saving a boundary.');
            setNotice('');
            return;
        }
        if (!String(boundaryDraft.asset_path || '').trim() && !String(boundaryDraft.inline_svg || '').trim()) {
            setError('Boundary asset path or inline SVG is required.');
            setNotice('');
            return;
        }
        setBoundarySaving(true);
        setError('');
        setNotice('');
        try {
            await apiPost('/api/admin/seat-boundaries', {
                seat_key: String(draft.seat_key || '').trim() || null,
                seat_type: String(draft.seat_type || 'mla').trim(),
                seat_name: seatName,
                state: String(draft.state || '').trim(),
                asset_type: String(boundaryDraft.asset_type || 'svg').trim(),
                asset_path: String(boundaryDraft.asset_path || '').trim(),
                inline_svg: String(boundaryDraft.inline_svg || '').trim(),
                metadata: { aspect_ratio: String(boundaryDraft.aspect_ratio || '100 / 72').trim() },
                status: 'verified',
            });
            await loadWorkflow(String(draft.seat_key || '').trim() || `${draft.seat_type}:${seatName}`);
            setNotice(`Saved real boundary for ${seatName}`);
        } catch (err) {
            setError(err.message || 'Unable to save boundary.');
        } finally {
            setBoundarySaving(false);
        }
    }

    return (
        <div style={{ display: 'grid', gridTemplateColumns: '320px minmax(0, 1fr)', gap: '1rem', alignItems: 'start' }}>
            <section style={{ ...CARD, padding: 18 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <div>
                        <div style={{ fontSize: '0.8rem', color: '#6b7f76', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>Seats</div>
                        <h2 style={{ margin: '4px 0 0', fontSize: '1rem', color: '#1a2e28' }}>Map Readiness</h2>
                    </div>
                    <button onClick={startNewSeat} style={SMALL_BTN}>+ New seat</button>
                </div>

                {loading ? (
                    <div style={{ color: '#6b7f76', fontSize: '0.9rem' }}>Loading seat workflows…</div>
                ) : (
                    <div style={{ display: 'grid', gap: 10 }}>
                        {items.map((item) => {
                            const active = item.seat_key === selectedKey;
                            return (
                                <button
                                    key={item.seat_key}
                                    onClick={() => selectSeat(item)}
                                    style={{
                                        textAlign: 'left',
                                        padding: 14,
                                        borderRadius: 12,
                                        border: active ? '1px solid #006a4d' : '1px solid #e2ebe5',
                                        background: active ? 'rgba(0,106,77,0.06)' : '#fff',
                                        cursor: 'pointer',
                                    }}
                                >
                                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                                        <strong style={{ color: '#1a2e28', fontSize: '0.92rem' }}>{item.seat_name}</strong>
                                        <span style={{ fontSize: '0.72rem', color: '#6b7f76', textTransform: 'uppercase', fontWeight: 700 }}>
                                            {item.seat_type === 'mla' ? 'MLA' : 'MP'}
                                        </span>
                                    </div>
                                    <div style={{ marginTop: 4, fontSize: '0.76rem', color: '#6b7f76' }}>{item.seat_key}</div>
                                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                                        <span style={{ ...badgeStyle(item.geography_ready ? 'ready' : 'warn'), fontSize: '0.72rem', padding: '3px 7px', borderRadius: 999 }}>
                                            {item.geography_ready ? 'Geography ready' : 'Needs geography'}
                                        </span>
                                        <span style={{ ...badgeStyle(item.map_ready ? 'ready' : 'neutral'), fontSize: '0.72rem', padding: '3px 7px', borderRadius: 999 }}>
                                            {item.map_ready ? 'Map ready' : 'No map yet'}
                                        </span>
                                    </div>
                                </button>
                            );
                        })}
                        {items.length === 0 && (
                            <div style={{ padding: 14, border: '1px dashed #d7e3dc', borderRadius: 12, color: '#6b7f76', fontSize: '0.88rem' }}>
                                No seats found yet. Start with a seat that already has geography or active tenants.
                            </div>
                        )}
                    </div>
                )}
            </section>

            <section style={{ ...CARD, padding: 18 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18, gap: 12 }}>
                    <div>
                        <div style={{ fontSize: '0.8rem', color: '#6b7f76', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>Seat workflow</div>
                        <h2 style={{ margin: '4px 0 0', fontSize: '1rem', color: '#1a2e28' }}>
                            {draft.seat_name ? draft.seat_name : 'New seat map'}
                        </h2>
                    </div>
                    <button onClick={generateSeatMap} disabled={working} style={{ ...SMALL_BTN, background: '#006a4d', color: '#fff', borderColor: '#006a4d' }}>
                        {working ? 'Working…' : selectedSeat?.map_ready ? 'Regenerate map' : 'Generate map'}
                    </button>
                </div>

                {error && (
                    <div style={{ marginBottom: 12, padding: '10px 12px', borderRadius: 10, background: '#fff4f2', border: '1px solid #f1c6bc', color: '#a8432e', fontSize: '0.88rem' }}>
                        {error}
                    </div>
                )}
                {notice && (
                    <div style={{ marginBottom: 12, padding: '10px 12px', borderRadius: 10, background: '#eef9f4', border: '1px solid #bfdfcd', color: '#006a4d', fontSize: '0.88rem' }}>
                        {notice}
                    </div>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 14 }}>
                    <div>
                        <label style={LABEL}>Seat Key</label>
                        <input style={INPUT} value={draft.seat_key} onChange={(e) => setDraft((prev) => ({ ...prev, seat_key: e.target.value }))} placeholder="mla:belgaum-dakshin" />
                    </div>
                    <div>
                        <label style={LABEL}>Seat Type</label>
                        <select style={INPUT} value={draft.seat_type} onChange={(e) => setDraft((prev) => ({ ...prev, seat_type: e.target.value }))}>
                            <option value="mla">MLA</option>
                            <option value="mp">MP</option>
                        </select>
                    </div>
                    <div>
                        <label style={LABEL}>Seat Name</label>
                        <input style={INPUT} value={draft.seat_name} onChange={(e) => setDraft((prev) => ({ ...prev, seat_name: e.target.value }))} placeholder="Belgaum Dakshin" />
                    </div>
                    <div>
                        <label style={LABEL}>State</label>
                        <input style={INPUT} value={draft.state} onChange={(e) => setDraft((prev) => ({ ...prev, state: e.target.value }))} placeholder="Karnataka" />
                    </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12, marginTop: 18 }}>
                    <div style={{ ...CARD, padding: 14, boxShadow: 'none' }}>
                        <div style={{ ...LABEL, marginBottom: 4 }}>Shared geography</div>
                        <div style={{ fontSize: '1rem', color: draft.geography_ready ? '#006a4d' : '#8b6f1a', fontWeight: 700 }}>
                            {draft.geography_ready ? 'Ready' : 'Missing'}
                        </div>
                        <div style={{ fontSize: '0.82rem', color: '#6b7f76', marginTop: 4 }}>
                            {draft.assembly_count || 0} assemblies · {draft.locality_count || 0} localities
                        </div>
                    </div>
                    <div style={{ ...CARD, padding: 14, boxShadow: 'none' }}>
                        <div style={{ ...LABEL, marginBottom: 4 }}>Map status</div>
                        <div style={{ fontSize: '1rem', color: draft.map_ready ? '#006a4d' : '#6b7f76', fontWeight: 700 }}>
                            {draft.map_ready ? (draft.generated ? 'Fallback generated' : 'Boundary-backed') : 'Not created'}
                        </div>
                        <div style={{ fontSize: '0.82rem', color: '#6b7f76', marginTop: 4 }}>
                            {draft.map_status || '—'} · {draft.map_source || '—'}
                        </div>
                    </div>
                    <div style={{ ...CARD, padding: 14, boxShadow: 'none' }}>
                        <div style={{ ...LABEL, marginBottom: 4 }}>Tenants on seat</div>
                        <div style={{ fontSize: '1rem', color: '#1a2e28', fontWeight: 700 }}>
                            {draft.tenant_count || 0}
                        </div>
                        <div style={{ fontSize: '0.82rem', color: '#6b7f76', marginTop: 4 }}>
                            Shared seat map will serve all of them
                        </div>
                    </div>
                    <div style={{ ...CARD, padding: 14, boxShadow: 'none' }}>
                        <div style={{ ...LABEL, marginBottom: 4 }}>Real boundary</div>
                        <div style={{ fontSize: '1rem', color: draft.boundary_ready ? '#006a4d' : '#8b6f1a', fontWeight: 700 }}>
                            {draft.boundary_ready ? 'Available' : 'Missing'}
                        </div>
                        <div style={{ fontSize: '0.82rem', color: '#6b7f76', marginTop: 4 }}>
                            {draft.boundary_ready ? `${draft.boundary_type || 'svg'} · ${draft.boundary_source || 'admin'}` : 'Blob fallback only'}
                        </div>
                    </div>
                    <div style={{ ...CARD, padding: 14, boxShadow: 'none' }}>
                        <div style={{ ...LABEL, marginBottom: 4 }}>Workflow</div>
                        <div style={{ fontSize: '0.92rem', color: '#1a2e28', fontWeight: 700 }}>
                            {!draft.geography_ready ? 'Upload geography first' : draft.boundary_ready ? 'Ready for real map' : 'Ready, but fallback only'}
                        </div>
                        <div style={{ fontSize: '0.82rem', color: '#6b7f76', marginTop: 4 }}>
                            {draft.boundary_ready ? 'Generation will use real boundary' : 'Register a boundary to avoid fallback blob'}
                        </div>
                    </div>
                </div>

                {!draft.geography_ready ? (
                    <div style={{ marginTop: 18, padding: '14px 16px', borderRadius: 12, background: '#fff7e8', border: '1px solid #ead7aa', color: '#6f5a1e' }}>
                        <div style={{ fontWeight: 700, marginBottom: 6 }}>Shared geography is missing for this seat.</div>
                        <div style={{ fontSize: '0.9rem' }}>
                            Upload geography once for this seat, then come back here and generate the map in one click.
                        </div>
                        <div style={{ marginTop: 10 }}>
                            <Link href="/dashboard/geography" style={{ ...SMALL_BTN, textDecoration: 'none', display: 'inline-flex' }}>
                                Go to Geography Upload
                            </Link>
                        </div>
                    </div>
                ) : (
                    <div style={{ marginTop: 18, padding: '14px 16px', borderRadius: 12, background: '#f4fbf7', border: '1px solid #cfe6d8', color: '#365247' }}>
                        <div style={{ fontWeight: 700, marginBottom: 6 }}>
                            {draft.boundary_ready ? 'This seat can generate a proper boundary-backed map.' : 'This seat can generate automatically, but will fall back to a generated blob.'}
                        </div>
                        <div style={{ fontSize: '0.9rem' }}>
                            The system will reuse the shared seat geography, place locality hotspots, and save one shared seat map for every tenant on this constituency.
                        </div>
                    </div>
                )}

                <div style={{ marginTop: 22 }}>
                    <h3 style={{ margin: '0 0 10px', fontSize: '0.96rem', color: '#1a2e28' }}>Real boundary ingestion</h3>
                    <div style={{ padding: '14px 16px', borderRadius: 12, border: '1px solid #e2ebe5', background: '#fbfcfb' }}>
                        <div style={{ fontSize: '0.88rem', color: '#6b7f76', marginBottom: 12 }}>
                            Register a real SVG boundary for this seat. Once saved, one-click generation will use it automatically instead of the fallback blob.
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr 160px auto', gap: 12, alignItems: 'end' }}>
                            <div>
                                <label style={LABEL}>Asset Type</label>
                                <select style={INPUT} value={boundaryDraft.asset_type} onChange={(e) => setBoundaryDraft((prev) => ({ ...prev, asset_type: e.target.value }))}>
                                    <option value="svg">SVG</option>
                                    <option value="geojson">GeoJSON</option>
                                </select>
                            </div>
                            <div>
                                <label style={LABEL}>Asset Path</label>
                                <input style={INPUT} value={boundaryDraft.asset_path} onChange={(e) => setBoundaryDraft((prev) => ({ ...prev, asset_path: e.target.value }))} placeholder="/maps/mp/belagavi-outline.svg" />
                            </div>
                            <div>
                                <label style={LABEL}>Aspect Ratio</label>
                                <input style={INPUT} value={boundaryDraft.aspect_ratio} onChange={(e) => setBoundaryDraft((prev) => ({ ...prev, aspect_ratio: e.target.value }))} placeholder="100 / 72" />
                            </div>
                            <button onClick={saveBoundary} disabled={boundarySaving} style={SMALL_BTN}>
                                {boundarySaving ? 'Saving…' : 'Save boundary'}
                            </button>
                        </div>
                        <div style={{ marginTop: 12 }}>
                            <label style={LABEL}>Inline SVG (optional)</label>
                            <textarea
                                style={{ ...INPUT, minHeight: 96, resize: 'vertical' }}
                                value={boundaryDraft.inline_svg}
                                onChange={(e) => setBoundaryDraft((prev) => ({ ...prev, inline_svg: e.target.value }))}
                                placeholder="<svg>…</svg>"
                            />
                        </div>
                    </div>
                </div>

                <div style={{ marginTop: 22 }}>
                    <h3 style={{ margin: '0 0 10px', fontSize: '0.96rem', color: '#1a2e28' }}>Tenant usage</h3>
                    {draft.tenants?.length ? (
                        <div style={{ display: 'grid', gap: 10 }}>
                            {draft.tenants.map((tenant) => (
                                <div key={tenant.tenant_id} style={{ border: '1px solid #e2ebe5', borderRadius: 12, padding: '12px 14px', background: '#fbfcfb' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                                        <div>
                                            <div style={{ fontWeight: 700, color: '#1a2e28' }}>{tenant.name}</div>
                                            <div style={{ fontSize: '0.8rem', color: '#6b7f76', marginTop: 4 }}>
                                                Tenant ID {tenant.tenant_id}
                                            </div>
                                        </div>
                                        <span style={{ ...badgeStyle('neutral'), fontSize: '0.72rem', padding: '3px 7px', borderRadius: 999, textTransform: 'capitalize' }}>
                                            {tenant.account_stage || 'active'}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div style={{ padding: 14, border: '1px dashed #d7e3dc', borderRadius: 12, color: '#6b7f76', fontSize: '0.88rem' }}>
                            No active tenants are currently using this seat. You can still generate the shared map if geography exists.
                        </div>
                    )}
                </div>
            </section>
        </div>
    );
}
