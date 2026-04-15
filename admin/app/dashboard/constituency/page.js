'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { apiDelete, apiGet, apiPost, apiPut, apiUpload } from '@/lib/api';

const TABS = [
    { key: 'overview', label: 'Overview' },
    { key: 'political', label: 'Political' },
    { key: 'assembly', label: 'Assembly' },
    { key: 'economy', label: 'Economy' },
    { key: 'social', label: 'Social' },
    { key: 'culture', label: 'Culture & Heritage' },
    { key: 'challenges', label: 'Challenges' },
];

function pretty(v) {
    if (v === null || v === undefined || v === '') return '—';
    if (typeof v === 'number') return Number.isFinite(v) ? v.toLocaleString('en-IN') : String(v);
    return String(v);
}

function sectionPayload(tab, profile) {
    if (!profile || typeof profile !== 'object') return {};
    switch (tab) {
        case 'overview':
            return { meta: profile.meta || {}, geography: profile.geography || {}, demographics: profile.demographics || {} };
        case 'political':
            return { political_history: profile.political_history || {} };
        case 'assembly':
            return { assembly_segments: profile.assembly_segments || [], assembly_summary_2023: profile.assembly_summary_2023 || {} };
        case 'economy':
            return { economy: profile.economy || {}, infrastructure: profile.infrastructure || {} };
        case 'social':
            return { social_indicators: profile.social_indicators || {} };
        case 'culture':
            return { cultural_profile: profile.cultural_profile || {} };
        case 'challenges':
            return {
                key_challenges: profile.key_challenges || [],
                development_priorities: profile.development_priorities || [],
                notable_facts: profile.notable_facts || [],
            };
        default:
            return profile;
    }
}

function applySectionPatch(tab, current, patchObj) {
    const next = { ...(current || {}) };
    switch (tab) {
        case 'overview':
            next.meta = patchObj.meta || {};
            next.geography = patchObj.geography || {};
            next.demographics = patchObj.demographics || {};
            return next;
        case 'political':
            next.political_history = patchObj.political_history || {};
            return next;
        case 'assembly':
            next.assembly_segments = patchObj.assembly_segments || [];
            next.assembly_summary_2023 = patchObj.assembly_summary_2023 || {};
            return next;
        case 'economy':
            next.economy = patchObj.economy || {};
            next.infrastructure = patchObj.infrastructure || {};
            return next;
        case 'social':
            next.social_indicators = patchObj.social_indicators || {};
            return next;
        case 'culture':
            next.cultural_profile = patchObj.cultural_profile || {};
            return next;
        case 'challenges':
            next.key_challenges = patchObj.key_challenges || [];
            next.development_priorities = patchObj.development_priorities || [];
            next.notable_facts = patchObj.notable_facts || [];
            return next;
        default:
            return next;
    }
}

export default function ConstituencyIntelPage() {
    const [profiles, setProfiles] = useState([]);
    const [mps, setMps] = useState([]);
    const [selectedSlug, setSelectedSlug] = useState('');
    const [profile, setProfile] = useState(null);
    const [tab, setTab] = useState('overview');
    const [editMode, setEditMode] = useState(false);
    const [editorText, setEditorText] = useState('{}');
    const [busy, setBusy] = useState(false);
    const [msg, setMsg] = useState({ type: '', text: '' });

    const [genForm, setGenForm] = useState({
        constituency_name: '',
        state: '',
        tenant_id: '',
        constituency_type: 'Lok Sabha',
    });
    const [job, setJob] = useState({ id: '', status: '', progress: '', error: '' });
    const [uploading, setUploading] = useState(false);
    const uploadRef = useRef(null);

    const genFormReady = !!(genForm.constituency_name.trim() && genForm.state.trim() && genForm.tenant_id);

    const selectedProfileMeta = useMemo(
        () => profiles.find((p) => p.slug === selectedSlug) || null,
        [profiles, selectedSlug]
    );

    function show(type, text) {
        setMsg({ type, text });
        setTimeout(() => setMsg({ type: '', text: '' }), 5000);
    }

    async function loadProfiles() {
        const res = await apiGet('/api/admin/constituency-profiles');
        setProfiles(res.profiles || []);
    }

    async function loadProfile(slug) {
        if (!slug) return;
        setBusy(true);
        try {
            const p = await apiGet(`/api/admin/constituency-profiles/${slug}`);
            setProfile(p);
        } finally {
            setBusy(false);
        }
    }

    useEffect(() => {
        (async () => {
            try {
                const [pRes, mRes] = await Promise.all([
                    apiGet('/api/admin/constituency-profiles'),
                    apiGet('/api/admin/mps'),
                ]);
                setProfiles(pRes.profiles || []);
                setMps((mRes.mps || []).filter((x) => x.role !== 'admin' && x.tenant_id));
            } catch {
                show('error', 'Failed to load constituency data.');
            }
        })();
    }, []);

    useEffect(() => {
        setEditorText(JSON.stringify(sectionPayload(tab, profile), null, 2));
    }, [tab, profile]);

    useEffect(() => {
        if (!selectedSlug) {
            setProfile(null);
            return;
        }
        loadProfile(selectedSlug).catch(() => show('error', 'Failed to load selected profile.'));
    }, [selectedSlug]);

    useEffect(() => {
        if (!job.id || !job.status || job.status === 'done' || job.status === 'error') return;
        const poll = setInterval(async () => {
            try {
                const r = await apiGet(`/api/admin/profile-generate/${job.id}`);
                setJob((j) => ({ ...j, status: r.status, progress: r.progress || '', error: r.error || '' }));
                if (r.status === 'done') {
                    clearInterval(poll);
                    await loadProfiles();
                    if (r.slug) {
                        setSelectedSlug(r.slug);
                        show('success', `Profile generated: ${r.name || r.slug}`);
                    } else {
                        show('success', 'Profile generation completed.');
                    }
                } else if (r.status === 'error') {
                    clearInterval(poll);
                    show('error', r.error || 'Profile generation failed.');
                }
            } catch {
                clearInterval(poll);
                show('error', 'Failed to poll generation job.');
            }
        }, 2500);
        return () => clearInterval(poll);
    }, [job.id, job.status]);

    async function handlePdfUpload(e) {
        const file = e.target.files?.[0];
        if (!file) return;
        if (!genFormReady) {
            show('error', 'Fill constituency name, state, and linked MP tenant before uploading.');
            return;
        }
        setUploading(true);
        try {
            const params = new URLSearchParams({
                constituency_name: genForm.constituency_name.trim(),
                state: genForm.state.trim(),
                tenant_id: genForm.tenant_id,
                constituency_type: genForm.constituency_type || 'Lok Sabha',
            });
            const formData = new FormData();
            formData.append('file', file);
            // apiUpload only sets file — append query params to URL manually
            const { api } = await import('@/lib/api');
            const result = await api(`/api/admin/profile-upload?${params}`, {
                method: 'POST',
                body: formData,
                timeout: 120_000,
                maxRetries: 0,
            });
            if (result.profile) {
                setProfile(result.profile);
                await loadProfiles();
                if (result.slug) setSelectedSlug(result.slug);
                show('success', `PDF parsed and profile saved as "${result.slug}". Review and edit tabs below.`);
            }
        } catch (err) {
            show('error', err.message || 'PDF upload failed.');
        } finally {
            setUploading(false);
            // Reset file input so same file can be re-uploaded
            if (uploadRef.current) uploadRef.current.value = '';
        }
    }

    async function startGeneration() {
        const tid = Number(genForm.tenant_id);
        if (!genForm.constituency_name || !genForm.state || !tid) {
            show('error', 'Please fill constituency, state, and linked MP tenant.');
            return;
        }
        setBusy(true);
        try {
            const r = await apiPost('/api/admin/profile-generate', {
                constituency_name: genForm.constituency_name.trim(),
                state: genForm.state.trim(),
                tenant_id: tid,
                constituency_type: genForm.constituency_type || 'Lok Sabha',
            });
            setJob({ id: r.job_id, status: 'running', progress: 'Research started…', error: '' });
            show('success', 'AI generation started. This can take a few minutes.');
        } catch (e) {
            show('error', e.message || 'Failed to start generation.');
        } finally {
            setBusy(false);
        }
    }

    async function saveCurrentSection() {
        if (!selectedSlug || !profile) return;
        let parsed;
        try {
            parsed = JSON.parse(editorText);
        } catch {
            show('error', 'Section JSON is invalid. Please fix and try again.');
            return;
        }

        const nextProfile = applySectionPatch(tab, profile, parsed);
        setBusy(true);
        try {
            await apiPut(`/api/admin/constituency-profiles/${selectedSlug}`, nextProfile);
            setProfile(nextProfile);
            await loadProfiles();
            show('success', `Saved ${TABS.find((t) => t.key === tab)?.label || 'section'}.`);
        } catch (e) {
            show('error', e.message || 'Failed to save section.');
        } finally {
            setBusy(false);
        }
    }

    async function deleteProfile() {
        if (!selectedSlug) return;
        const ok = window.confirm(`Delete profile "${selectedSlug}"? This cannot be undone.`);
        if (!ok) return;
        setBusy(true);
        try {
            await apiDelete(`/api/admin/constituency-profiles/${selectedSlug}`);
            await loadProfiles();
            setSelectedSlug('');
            setProfile(null);
            show('success', 'Profile deleted.');
        } catch (e) {
            show('error', e.message || 'Failed to delete profile.');
        } finally {
            setBusy(false);
        }
    }

    const currentSectionData = sectionPayload(tab, profile);

    return (
        <div style={{ display: 'grid', gap: 16 }}>
            {msg.text && (
                <div className={`toast ${msg.type === 'success' ? 'toast-success' : 'toast-error'}`}>{msg.text}</div>
            )}

            <div className="glass-panel">
                <div className="section-title">Generate with AI</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.9fr 1fr 0.8fr auto', gap: 10 }}>
                    <input
                        className="form-input"
                        placeholder="Constituency name (e.g., Belagavi)"
                        value={genForm.constituency_name}
                        onChange={(e) => setGenForm((f) => ({ ...f, constituency_name: e.target.value }))}
                    />
                    <input
                        className="form-input"
                        placeholder="State"
                        value={genForm.state}
                        onChange={(e) => setGenForm((f) => ({ ...f, state: e.target.value }))}
                    />
                    <select
                        className="form-input"
                        value={genForm.tenant_id}
                        onChange={(e) => setGenForm((f) => ({ ...f, tenant_id: e.target.value }))}
                    >
                        <option value="">Link to MP tenant…</option>
                        {mps.map((mp) => (
                            <option key={mp.tenant_id} value={mp.tenant_id}>
                                {mp.display_name} · {mp.parliamentary_constituency}
                            </option>
                        ))}
                    </select>
                    <select
                        className="form-input"
                        value={genForm.constituency_type}
                        onChange={(e) => setGenForm((f) => ({ ...f, constituency_type: e.target.value }))}
                    >
                        <option value="Lok Sabha">Lok Sabha</option>
                        <option value="Assembly">Assembly</option>
                    </select>
                    <button className="btn-primary" onClick={startGeneration} disabled={busy || uploading}>
                        Generate
                    </button>
                    <button
                        className="btn-secondary"
                        onClick={() => uploadRef.current?.click()}
                        disabled={!genFormReady || busy || uploading}
                        title={genFormReady ? 'Upload a PDF to auto-parse into profile' : 'Fill constituency details first'}
                        style={{ whiteSpace: 'nowrap' }}
                    >
                        {uploading ? 'Parsing PDF…' : '📄 Upload PDF'}
                    </button>
                    <input
                        ref={uploadRef}
                        type="file"
                        accept=".pdf"
                        style={{ display: 'none' }}
                        onChange={handlePdfUpload}
                    />
                </div>
                {job.id && (
                    <div style={{ marginTop: 10, fontSize: '0.82rem', color: '#6b7f76' }}>
                        Job <strong>{job.id}</strong> · <strong>{job.status}</strong>
                        {job.progress ? ` · ${job.progress}` : ''}
                        {job.error ? ` · ${job.error}` : ''}
                    </div>
                )}
            </div>

            <div className="glass-panel">
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center', marginBottom: 10 }}>
                    <div className="section-title" style={{ marginBottom: 0, borderBottom: 'none', paddingBottom: 0 }}>
                        Profile Viewer
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                        <button className="btn-secondary" onClick={() => setEditMode((v) => !v)}>
                            {editMode ? 'Exit Edit Mode' : 'Edit Mode'}
                        </button>
                        <button className="btn-danger" onClick={deleteProfile} disabled={!selectedSlug || busy}>
                            Delete Profile
                        </button>
                    </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10, marginBottom: 12 }}>
                    <select className="form-input" value={selectedSlug} onChange={(e) => setSelectedSlug(e.target.value)}>
                        <option value="">Select a constituency profile…</option>
                        {profiles.map((p) => (
                            <option key={p.slug} value={p.slug}>
                                {p.name} ({p.state || '—'}) · {p.last_updated || 'no date'}
                            </option>
                        ))}
                    </select>
                    {selectedProfileMeta && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span className="badge badge-slate">{selectedProfileMeta.assembly_segments_count || 0} assembly segments</span>
                            {selectedProfileMeta.tenant_name ? (
                                <span className="badge badge-green">{selectedProfileMeta.tenant_name}</span>
                            ) : (
                                <span className="badge badge-amber">Unlinked tenant</span>
                            )}
                        </div>
                    )}
                </div>

                {!profile ? (
                    <div className="empty-state">
                        <div className="empty-state-title">No profile selected</div>
                        <div className="empty-state-desc">Generate a profile or choose one from the list to view/edit.</div>
                    </div>
                ) : (
                    <>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
                            {TABS.map((t) => (
                                <button
                                    key={t.key}
                                    className={tab === t.key ? 'btn-primary' : 'btn-secondary'}
                                    onClick={() => setTab(t.key)}
                                    style={{ padding: '7px 12px', fontSize: '0.78rem' }}
                                >
                                    {t.label}
                                </button>
                            ))}
                        </div>

                        {!editMode ? (
                            <div
                                style={{
                                    border: '1px solid #e2ebe5',
                                    borderRadius: 10,
                                    background: '#f8faf9',
                                    padding: 14,
                                    maxHeight: 520,
                                    overflow: 'auto',
                                }}
                            >
                                {tab === 'overview' && (
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
                                        <div className="stat-card"><div className="form-label">Name</div><div>{pretty(profile.meta?.name)}</div></div>
                                        <div className="stat-card"><div className="form-label">State</div><div>{pretty(profile.meta?.state)}</div></div>
                                        <div className="stat-card"><div className="form-label">Type</div><div>{pretty(profile.meta?.type)}</div></div>
                                        <div className="stat-card"><div className="form-label">Electors 2024</div><div>{pretty(profile.meta?.total_electors_2024)}</div></div>
                                        <div className="stat-card"><div className="form-label">Area (sq km)</div><div>{pretty(profile.geography?.area_sq_km)}</div></div>
                                        <div className="stat-card"><div className="form-label">Population</div><div>{pretty(profile.demographics?.total_population)}</div></div>
                                        <div className="stat-card"><div className="form-label">Literacy</div><div>{pretty(profile.demographics?.literacy?.overall_percent)}%</div></div>
                                        <div className="stat-card"><div className="form-label">Primary Language</div><div>{pretty(profile.demographics?.languages?.primary)}</div></div>
                                    </div>
                                )}
                                {tab !== 'overview' && (
                                    <pre style={{ margin: 0, fontSize: '0.8rem', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                                        {JSON.stringify(currentSectionData, null, 2)}
                                    </pre>
                                )}
                            </div>
                        ) : (
                            <div>
                                <textarea
                                    className="form-input"
                                    rows={20}
                                    style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace', fontSize: '0.8rem' }}
                                    value={editorText}
                                    onChange={(e) => setEditorText(e.target.value)}
                                />
                                <div style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span style={{ fontSize: '0.78rem', color: '#6b7f76' }}>
                                        Edit JSON for the current tab only, then save section.
                                    </span>
                                    <button className="btn-primary" onClick={saveCurrentSection} disabled={busy || !selectedSlug}>
                                        Save Section
                                    </button>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
