'use client';

import { useEffect, useMemo, useState } from 'react';
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

function blankFeature() {
    return {
        feature_key: '',
        label: '',
        aliases: [''],
        anchor: { x: '', y: '' },
    };
}

function blankManifest() {
    return {
        seat_key: '',
        seat_type: 'mla',
        seat_name: '',
        state: '',
        aliases: [''],
        asset: { type: 'svg', path: '', aspect_ratio: '' },
        features: [blankFeature()],
        fallback_anchors: [{ x: '', y: '' }],
        status: 'draft',
        version: null,
    };
}

function normalizeForForm(manifest) {
    if (!manifest) return blankManifest();
    return {
        seat_key: manifest.seat_key || '',
        seat_type: manifest.seat_type || 'mla',
        seat_name: manifest.seat_name || '',
        state: manifest.state || '',
        aliases: (manifest.aliases && manifest.aliases.length ? manifest.aliases : ['']).map((alias) => alias || ''),
        asset: {
            type: manifest.asset?.type || 'svg',
            path: manifest.asset?.path || '',
            aspect_ratio: manifest.asset?.aspect_ratio || '',
        },
        features: (manifest.features && manifest.features.length ? manifest.features : [blankFeature()]).map((feature) => ({
            feature_key: feature.feature_key || '',
            label: feature.label || '',
            aliases: (feature.aliases && feature.aliases.length ? feature.aliases : ['']).map((alias) => alias || ''),
            anchor: {
                x: feature.anchor?.x ?? '',
                y: feature.anchor?.y ?? '',
            },
        })),
        fallback_anchors: (manifest.fallback_anchors && manifest.fallback_anchors.length ? manifest.fallback_anchors : [{ x: '', y: '' }]).map((anchor) => ({
            x: anchor?.x ?? '',
            y: anchor?.y ?? '',
        })),
        status: manifest.status || 'draft',
        version: manifest.version ?? null,
    };
}

function cleanAliases(values) {
    return (values || []).map((item) => String(item || '').trim()).filter(Boolean);
}

function cleanAnchors(values) {
    return (values || [])
        .map((anchor) => ({
            x: Number(anchor.x),
            y: Number(anchor.y),
        }))
        .filter((anchor) => Number.isFinite(anchor.x) && Number.isFinite(anchor.y));
}

function buildPayload(form) {
    return {
        seat_key: String(form.seat_key || '').trim(),
        seat_type: String(form.seat_type || 'mla').trim(),
        seat_name: String(form.seat_name || '').trim(),
        state: String(form.state || '').trim(),
        aliases: cleanAliases(form.aliases),
        asset: {
            type: String(form.asset?.type || 'svg').trim(),
            path: String(form.asset?.path || '').trim(),
            aspect_ratio: String(form.asset?.aspect_ratio || '').trim(),
        },
        features: (form.features || []).map((feature) => ({
            feature_key: String(feature.feature_key || '').trim(),
            label: String(feature.label || '').trim(),
            aliases: cleanAliases(feature.aliases),
            anchor: {
                x: Number(feature.anchor?.x),
                y: Number(feature.anchor?.y),
            },
        })).filter((feature) =>
            feature.feature_key &&
            feature.label &&
            feature.aliases.length > 0 &&
            Number.isFinite(feature.anchor.x) &&
            Number.isFinite(feature.anchor.y)
        ),
        fallback_anchors: cleanAnchors(form.fallback_anchors),
        status: String(form.status || 'draft').trim(),
        version: form.version ?? null,
    };
}

function validate(form) {
    const payload = buildPayload(form);
    const errors = [];
    if (!payload.seat_key) errors.push('Seat key is required.');
    if (!payload.seat_name) errors.push('Seat name is required.');
    if (!payload.asset.path) errors.push('Asset path is required.');
    if (!['draft', 'verified', 'live'].includes(payload.status)) errors.push('Status must be draft, verified, or live.');

    const aliasSet = new Set();
    payload.aliases.forEach((alias) => {
        const key = alias.toLowerCase();
        if (aliasSet.has(key)) errors.push(`Duplicate seat alias: ${alias}`);
        aliasSet.add(key);
    });

    payload.features.forEach((feature) => {
        const featureAliasSet = new Set();
        feature.aliases.forEach((alias) => {
            const key = alias.toLowerCase();
            if (featureAliasSet.has(key)) errors.push(`Duplicate alias in feature ${feature.feature_key}: ${alias}`);
            featureAliasSet.add(key);
        });
        if (feature.anchor.x < 0 || feature.anchor.x > 100 || feature.anchor.y < 0 || feature.anchor.y > 100) {
            errors.push(`Feature ${feature.feature_key} anchor must stay within 0–100.`);
        }
    });

    payload.fallback_anchors.forEach((anchor, index) => {
        if (anchor.x < 0 || anchor.x > 100 || anchor.y < 0 || anchor.y > 100) {
            errors.push(`Fallback anchor ${index + 1} must stay within 0–100.`);
        }
    });

    return { payload, errors };
}

export default function SeatMapsPage() {
    const [items, setItems] = useState([]);
    const [selectedKey, setSelectedKey] = useState('');
    const [form, setForm] = useState(blankManifest());
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');

    useEffect(() => {
        let cancelled = false;
        (async () => {
            setLoading(true);
            setError('');
            try {
                const response = await apiGet('/api/admin/seat-maps');
                const nextItems = response.items || [];
                if (cancelled) return;
                setItems(nextItems);
                if (nextItems.length > 0) {
                    setSelectedKey(nextItems[0].seat_key);
                    setForm(normalizeForForm(nextItems[0]));
                } else {
                    setForm(blankManifest());
                }
            } catch (err) {
                if (!cancelled) setError(err.message || 'Unable to load seat maps.');
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    const selectedManifest = useMemo(
        () => items.find((item) => item.seat_key === selectedKey) || null,
        [items, selectedKey]
    );

    function updateField(field, value) {
        setForm((prev) => ({ ...prev, [field]: value }));
    }

    function updateAsset(field, value) {
        setForm((prev) => ({ ...prev, asset: { ...prev.asset, [field]: value } }));
    }

    function updateAliases(nextAliases) {
        setForm((prev) => ({ ...prev, aliases: nextAliases }));
    }

    function updateFeature(index, nextFeature) {
        setForm((prev) => ({
            ...prev,
            features: prev.features.map((feature, i) => (i === index ? nextFeature : feature)),
        }));
    }

    function addFeature() {
        setForm((prev) => ({ ...prev, features: [...prev.features, blankFeature()] }));
    }

    function removeFeature(index) {
        setForm((prev) => ({
            ...prev,
            features: prev.features.length === 1 ? [blankFeature()] : prev.features.filter((_, i) => i !== index),
        }));
    }

    function addFallbackAnchor() {
        setForm((prev) => ({ ...prev, fallback_anchors: [...prev.fallback_anchors, { x: '', y: '' }] }));
    }

    function removeFallbackAnchor(index) {
        setForm((prev) => ({
            ...prev,
            fallback_anchors: prev.fallback_anchors.length === 1 ? [{ x: '', y: '' }] : prev.fallback_anchors.filter((_, i) => i !== index),
        }));
    }

    function startNewManifest() {
        setSelectedKey('');
        setNotice('');
        setError('');
        setForm(blankManifest());
    }

    function selectManifest(manifest) {
        setSelectedKey(manifest.seat_key);
        setNotice('');
        setError('');
        setForm(normalizeForForm(manifest));
    }

    async function saveManifest() {
        const { payload, errors } = validate(form);
        if (errors.length > 0) {
            setError(errors[0]);
            setNotice('');
            return;
        }
        setSaving(true);
        setError('');
        setNotice('');
        try {
            const response = await apiPost('/api/admin/seat-maps', payload);
            const saved = response.manifest;
            setItems((prev) => {
                const others = prev.filter((item) => item.seat_key !== saved.seat_key);
                return [...others, saved].sort((a, b) => String(a.seat_key).localeCompare(String(b.seat_key)));
            });
            setSelectedKey(saved.seat_key);
            setForm(normalizeForForm(saved));
            setNotice(`Saved ${saved.seat_key}`);
        } catch (err) {
            setError(err.message || 'Unable to save seat map.');
        } finally {
            setSaving(false);
        }
    }

    return (
        <div style={{ display: 'grid', gridTemplateColumns: '320px minmax(0, 1fr)', gap: '1rem', alignItems: 'start' }}>
            <section style={{ ...CARD, padding: 18 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <div>
                        <div style={{ fontSize: '0.8rem', color: '#6b7f76', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>Registry</div>
                        <h2 style={{ margin: '4px 0 0', fontSize: '1rem', color: '#1a2e28' }}>Seat Manifests</h2>
                    </div>
                    <button onClick={startNewManifest} style={SMALL_BTN}>+ New</button>
                </div>

                {loading ? (
                    <div style={{ color: '#6b7f76', fontSize: '0.9rem' }}>Loading seat maps…</div>
                ) : (
                    <div style={{ display: 'grid', gap: 10 }}>
                        {items.map((item) => {
                            const active = item.seat_key === selectedKey;
                            return (
                                <button
                                    key={item.seat_key}
                                    onClick={() => selectManifest(item)}
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
                                        <span style={{ fontSize: '0.72rem', color: item.status === 'live' ? '#006a4d' : '#8b6f1a', textTransform: 'uppercase', fontWeight: 700 }}>
                                            {item.status}
                                        </span>
                                    </div>
                                    <div style={{ marginTop: 4, fontSize: '0.76rem', color: '#6b7f76' }}>{item.seat_key}</div>
                                    <div style={{ marginTop: 6, fontSize: '0.78rem', color: '#365247' }}>
                                        {(item.features || []).length} features · v{item.version || 1} · {item.source || 'repo'}
                                    </div>
                                </button>
                            );
                        })}
                        {items.length === 0 && (
                            <div style={{ padding: 14, border: '1px dashed #d7e3dc', borderRadius: 12, color: '#6b7f76', fontSize: '0.88rem' }}>
                                No seat manifests yet.
                            </div>
                        )}
                    </div>
                )}
            </section>

            <section style={{ ...CARD, padding: 18 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
                    <div>
                        <div style={{ fontSize: '0.8rem', color: '#6b7f76', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>Editor</div>
                        <h2 style={{ margin: '4px 0 0', fontSize: '1rem', color: '#1a2e28' }}>
                            {selectedManifest ? selectedManifest.seat_name : 'New seat map'}
                        </h2>
                    </div>
                    <button onClick={saveManifest} disabled={saving} style={{ ...SMALL_BTN, background: '#006a4d', color: '#fff', borderColor: '#006a4d' }}>
                        {saving ? 'Saving…' : 'Save manifest'}
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
                        <input style={INPUT} value={form.seat_key} onChange={(e) => updateField('seat_key', e.target.value)} placeholder="mla:belgaum-dakshin" />
                    </div>
                    <div>
                        <label style={LABEL}>Seat Type</label>
                        <select style={INPUT} value={form.seat_type} onChange={(e) => updateField('seat_type', e.target.value)}>
                            <option value="mla">MLA</option>
                            <option value="mp">MP</option>
                        </select>
                    </div>
                    <div>
                        <label style={LABEL}>Seat Name</label>
                        <input style={INPUT} value={form.seat_name} onChange={(e) => updateField('seat_name', e.target.value)} placeholder="Belgaum Dakshin" />
                    </div>
                    <div>
                        <label style={LABEL}>State</label>
                        <input style={INPUT} value={form.state} onChange={(e) => updateField('state', e.target.value)} placeholder="Karnataka" />
                    </div>
                    <div>
                        <label style={LABEL}>Status</label>
                        <select style={INPUT} value={form.status} onChange={(e) => updateField('status', e.target.value)}>
                            <option value="draft">Draft</option>
                            <option value="verified">Verified</option>
                            <option value="live">Live</option>
                        </select>
                    </div>
                    <div>
                        <label style={LABEL}>Version</label>
                        <input style={INPUT} value={form.version ?? ''} readOnly placeholder="Auto" />
                    </div>
                </div>

                <div style={{ marginTop: 18 }}>
                    <label style={LABEL}>Seat Aliases</label>
                    <textarea
                        style={{ ...INPUT, minHeight: 90, resize: 'vertical' }}
                        value={form.aliases.join('\n')}
                        onChange={(e) => updateAliases(e.target.value.split('\n'))}
                        placeholder={'Belgaum Dakshin\nBelgaum South\nBelagavi South'}
                    />
                </div>

                <div style={{ marginTop: 18, display: 'grid', gridTemplateColumns: '1fr 160px 140px', gap: 14 }}>
                    <div>
                        <label style={LABEL}>Asset Path</label>
                        <input style={INPUT} value={form.asset.path} onChange={(e) => updateAsset('path', e.target.value)} placeholder="/maps/mla/belgaum-dakshin-outline.svg" />
                    </div>
                    <div>
                        <label style={LABEL}>Asset Type</label>
                        <input style={INPUT} value={form.asset.type} onChange={(e) => updateAsset('type', e.target.value)} placeholder="svg" />
                    </div>
                    <div>
                        <label style={LABEL}>Aspect Ratio</label>
                        <input style={INPUT} value={form.asset.aspect_ratio} onChange={(e) => updateAsset('aspect_ratio', e.target.value)} placeholder="72 / 63" />
                    </div>
                </div>

                <div style={{ marginTop: 24 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                        <h3 style={{ margin: 0, fontSize: '0.96rem', color: '#1a2e28' }}>Features</h3>
                        <button onClick={addFeature} style={SMALL_BTN}>+ Feature</button>
                    </div>
                    <div style={{ display: 'grid', gap: 12 }}>
                        {form.features.map((feature, index) => (
                            <div key={index} style={{ border: '1px solid #e2ebe5', borderRadius: 12, padding: 14, background: '#fbfcfb' }}>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 90px 90px auto', gap: 10, alignItems: 'end' }}>
                                    <div>
                                        <label style={LABEL}>Feature Key</label>
                                        <input
                                            style={INPUT}
                                            value={feature.feature_key}
                                            onChange={(e) => updateFeature(index, { ...feature, feature_key: e.target.value })}
                                            placeholder="nath-pai-circle"
                                        />
                                    </div>
                                    <div>
                                        <label style={LABEL}>Label</label>
                                        <input
                                            style={INPUT}
                                            value={feature.label}
                                            onChange={(e) => updateFeature(index, { ...feature, label: e.target.value })}
                                            placeholder="Nath Pai Circle"
                                        />
                                    </div>
                                    <div>
                                        <label style={LABEL}>X</label>
                                        <input
                                            style={INPUT}
                                            value={feature.anchor.x}
                                            onChange={(e) => updateFeature(index, { ...feature, anchor: { ...feature.anchor, x: e.target.value } })}
                                            placeholder="68"
                                        />
                                    </div>
                                    <div>
                                        <label style={LABEL}>Y</label>
                                        <input
                                            style={INPUT}
                                            value={feature.anchor.y}
                                            onChange={(e) => updateFeature(index, { ...feature, anchor: { ...feature.anchor, y: e.target.value } })}
                                            placeholder="40"
                                        />
                                    </div>
                                    <button onClick={() => removeFeature(index)} style={{ ...SMALL_BTN, color: '#a8432e' }}>Remove</button>
                                </div>
                                <div style={{ marginTop: 10 }}>
                                    <label style={LABEL}>Aliases</label>
                                    <textarea
                                        style={{ ...INPUT, minHeight: 72, resize: 'vertical' }}
                                        value={feature.aliases.join('\n')}
                                        onChange={(e) => updateFeature(index, { ...feature, aliases: e.target.value.split('\n') })}
                                        placeholder={'nath pai circle\nnath pai circle shahapur belagavi'}
                                    />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                <div style={{ marginTop: 24 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                        <h3 style={{ margin: 0, fontSize: '0.96rem', color: '#1a2e28' }}>Fallback Anchors</h3>
                        <button onClick={addFallbackAnchor} style={SMALL_BTN}>+ Anchor</button>
                    </div>
                    <div style={{ display: 'grid', gap: 10 }}>
                        {form.fallback_anchors.map((anchor, index) => (
                            <div key={index} style={{ display: 'grid', gridTemplateColumns: '120px 120px auto', gap: 10, alignItems: 'end' }}>
                                <div>
                                    <label style={LABEL}>X</label>
                                    <input
                                        style={INPUT}
                                        value={anchor.x}
                                        onChange={(e) => {
                                            const next = form.fallback_anchors.map((item, i) => i === index ? { ...item, x: e.target.value } : item);
                                            setForm((prev) => ({ ...prev, fallback_anchors: next }));
                                        }}
                                        placeholder="25"
                                    />
                                </div>
                                <div>
                                    <label style={LABEL}>Y</label>
                                    <input
                                        style={INPUT}
                                        value={anchor.y}
                                        onChange={(e) => {
                                            const next = form.fallback_anchors.map((item, i) => i === index ? { ...item, y: e.target.value } : item);
                                            setForm((prev) => ({ ...prev, fallback_anchors: next }));
                                        }}
                                        placeholder="26"
                                    />
                                </div>
                                <button onClick={() => removeFallbackAnchor(index)} style={{ ...SMALL_BTN, color: '#a8432e' }}>Remove</button>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
        </div>
    );
}
