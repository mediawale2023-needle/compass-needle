'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { apiDelete, apiGet, apiPost, apiPut } from '@/lib/api';

const TABS = [
    { key: 'overview', label: 'Overview' },
    { key: 'political', label: 'Political' },
    { key: 'assembly', label: 'Assembly' },
    { key: 'economy', label: 'Economy' },
    { key: 'social', label: 'Social' },
    { key: 'culture', label: 'Culture & Heritage' },
    { key: 'challenges', label: 'Challenges' },
];

const CONSTITUENCY_SOURCE_TYPES = [
    'const_overview',
    'const_political',
    'const_assembly',
    'const_economy',
    'const_social',
    'const_culture',
    'const_challenge',
    'const_priority',
    'const_fact',
];

function pretty(v) {
    if (v === null || v === undefined || v === '') return '—';
    if (typeof v === 'number') return Number.isFinite(v) ? v.toLocaleString('en-IN') : String(v);
    return String(v);
}

function asArray(value) {
    return Array.isArray(value) ? value : [];
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

function isPresent(value) {
    if (value === null || value === undefined) return false;
    if (typeof value === 'number') return Number.isFinite(value) && value !== 0;
    if (typeof value === 'string') return value.trim().length > 0;
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === 'object') return Object.keys(value).length > 0;
    return Boolean(value);
}

function computeCompleteness(profile) {
    if (!profile) return { score: 0, done: 0, total: 0, checks: [] };
    const meta = profile.meta || {};
    const checks = [
        ['Tenant linked', isPresent(meta.tenant_id), 'Required for MP frontend grounding.'],
        ['Identity', isPresent(meta.name) && isPresent(meta.state) && isPresent(meta.type), 'Name, state, and constituency type.'],
        ['Electors', isPresent(meta.total_electors_2024), 'Latest voter base for context.'],
        ['Geography', isPresent(profile.geography), 'Terrain, districts, talukas, rivers, climate.'],
        ['Demographics', isPresent(profile.demographics), 'Population, literacy, language, community context.'],
        ['Assembly segments', asArray(profile.assembly_segments).length >= 1, 'Assembly list with MLA/party where available.'],
        ['Political history', isPresent(profile.political_history), 'Current MP, past MPs, political character.'],
        ['Economy and infrastructure', isPresent(profile.economy) || isPresent(profile.infrastructure), 'Local economy, connectivity, institutions.'],
        ['Social indicators', isPresent(profile.social_indicators), 'Schemes and development indicators.'],
        ['Culture and heritage', isPresent(profile.cultural_profile), 'Local identity, festivals, heritage, personalities.'],
        ['Challenges', asArray(profile.key_challenges).length >= 3, 'Issue anchors for letters/research.'],
        ['Priorities', asArray(profile.development_priorities).length >= 3, 'Development asks for drafting.'],
        ['Notable facts', asArray(profile.notable_facts).length >= 3, 'Useful constituency references.'],
    ].map(([label, done, hint]) => ({ label, done: Boolean(done), hint }));
    const done = checks.filter(c => c.done).length;
    return { score: Math.round((done / checks.length) * 100), done, total: checks.length, checks };
}

function getPrimaryLanguage(profile) {
    const langs = profile?.demographics?.languages || {};
    if (langs.primary) return langs.primary;
    const pctEntries = Object.entries(langs)
        .filter(([k, v]) => k.endsWith('_percent') && typeof v === 'number')
        .sort((a, b) => b[1] - a[1]);
    if (!pctEntries.length) return '';
    return pctEntries[0][0].replace('_percent', '').replace(/_/g, ' ');
}

function ReadinessCard({ label, value, detail, tone = 'green' }) {
    const color = tone === 'red' ? '#dc2626' : tone === 'amber' ? '#d97706' : tone === 'blue' ? '#2563eb' : '#006a4d';
    return (
        <div className="stat-card" style={{ minHeight: 104 }}>
            <div className="form-label">{label}</div>
            <div style={{ color, fontSize: '1.35rem', fontWeight: 850, marginTop: 7 }}>{value}</div>
            <div style={{ color: '#6b7f76', fontSize: '0.76rem', marginTop: 7, lineHeight: 1.4 }}>{detail}</div>
        </div>
    );
}

function ValueList({ items }) {
    const rows = asArray(items);
    if (!rows.length) return <div style={{ color: '#6b7f76', fontSize: '0.82rem' }}>No entries yet.</div>;
    return (
        <div style={{ display: 'grid', gap: 8 }}>
            {rows.map((item, i) => {
                const obj = item && typeof item === 'object' ? item : null;
                const title = obj ? (obj.title || obj.name || obj.sector || obj.year || `Item ${i + 1}`) : item;
                const detail = obj
                    ? (item.detail || item.note || item.significance || item.details || item.party || '')
                    : '';
                return (
                    <div key={i} style={{ background: '#fff', border: '1px solid #e2ebe5', borderRadius: 10, padding: '10px 12px' }}>
                        <div style={{ color: '#1a2e28', fontWeight: 800, fontSize: '0.84rem' }}>{pretty(title)}</div>
                        {detail && <div style={{ color: '#6b7f76', fontSize: '0.76rem', marginTop: 4, lineHeight: 1.45 }}>{pretty(detail)}</div>}
                    </div>
                );
            })}
        </div>
    );
}

function KeyValueGrid({ data }) {
    const entries = Object.entries(data || {}).filter(([, v]) => isPresent(v));
    if (!entries.length) return <div style={{ color: '#6b7f76', fontSize: '0.82rem' }}>No data yet.</div>;
    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 10 }}>
            {entries.map(([k, v]) => (
                <div key={k} style={{ background: '#fff', border: '1px solid #e2ebe5', borderRadius: 10, padding: '10px 12px' }}>
                    <div className="form-label">{k.replace(/_/g, ' ')}</div>
                    <div style={{ color: '#1a2e28', fontSize: '0.86rem', lineHeight: 1.45 }}>
                        {typeof v === 'object' ? JSON.stringify(v, null, 2) : pretty(v)}
                    </div>
                </div>
            ))}
        </div>
    );
}

function SectionView({ tab, profile }) {
    if (tab === 'overview') {
        return (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 10 }}>
                <div className="stat-card"><div className="form-label">Name</div><div>{pretty(profile.meta?.name)}</div></div>
                <div className="stat-card"><div className="form-label">State</div><div>{pretty(profile.meta?.state)}</div></div>
                <div className="stat-card"><div className="form-label">Type</div><div>{pretty(profile.meta?.type)}</div></div>
                <div className="stat-card"><div className="form-label">Electors 2024</div><div>{pretty(profile.meta?.total_electors_2024)}</div></div>
                <div className="stat-card"><div className="form-label">Area (sq km)</div><div>{pretty(profile.geography?.area_sq_km)}</div></div>
                <div className="stat-card"><div className="form-label">Population</div><div>{pretty(profile.demographics?.total_population)}</div></div>
                <div className="stat-card"><div className="form-label">Literacy</div><div>{pretty(profile.demographics?.literacy?.overall_percent)}%</div></div>
                <div className="stat-card"><div className="form-label">Primary Language</div><div style={{ textTransform: 'capitalize' }}>{pretty(getPrimaryLanguage(profile))}</div></div>
            </div>
        );
    }

    if (tab === 'political') {
        const pol = profile.political_history || {};
        return (
            <div style={{ display: 'grid', gap: 12 }}>
                <KeyValueGrid data={pol.current_mp || {}} />
                {pol.political_character && <div style={{ color: '#1a2e28', lineHeight: 1.55 }}>{pol.political_character}</div>}
                <ValueList items={pol.key_political_issues || []} />
                <ValueList items={pol.past_mps || pol.election_results || []} />
            </div>
        );
    }

    if (tab === 'assembly') {
        return (
            <div style={{ display: 'grid', gap: 12 }}>
                <KeyValueGrid data={profile.assembly_summary_2023 || {}} />
                <div style={{ overflowX: 'auto' }}>
                    <table className="data-table">
                        <thead><tr><th>Segment</th><th>MLA</th><th>Party</th><th>Margin</th><th>Note</th></tr></thead>
                        <tbody>
                            {asArray(profile.assembly_segments).map((s, i) => (
                                <tr key={i}>
                                    <td>{pretty(s.name)}</td>
                                    <td>{pretty(s.mla)}</td>
                                    <td>{pretty(s.party)}</td>
                                    <td>{pretty(s.winning_margin)}</td>
                                    <td>{pretty(s.note)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    }

    if (tab === 'economy') {
        return (
            <div style={{ display: 'grid', gap: 12 }}>
                {profile.economy?.overview && <div style={{ color: '#1a2e28', lineHeight: 1.55 }}>{profile.economy.overview}</div>}
                <ValueList items={profile.economy?.industries || []} />
                <KeyValueGrid data={profile.infrastructure || {}} />
            </div>
        );
    }

    if (tab === 'social') return <KeyValueGrid data={profile.social_indicators || {}} />;
    if (tab === 'culture') return <KeyValueGrid data={profile.cultural_profile || {}} />;
    return (
        <div style={{ display: 'grid', gap: 14 }}>
            <div><div className="form-label">Key Challenges</div><ValueList items={profile.key_challenges || []} /></div>
            <div><div className="form-label">Development Priorities</div><ValueList items={profile.development_priorities || []} /></div>
            <div><div className="form-label">Notable Facts</div><ValueList items={profile.notable_facts || []} /></div>
        </div>
    );
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
    const [brainStats, setBrainStats] = useState(null);
    const [indexJob, setIndexJob] = useState({ id: '', status: '', error: '' });
    const [groundingQuery, setGroundingQuery] = useState('');
    const [groundingBusy, setGroundingBusy] = useState(false);
    const [groundingResults, setGroundingResults] = useState(null);

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
    const tenantId = Number(profile?.meta?.tenant_id || selectedProfileMeta?.tenant_id || 0);
    const completeness = useMemo(() => computeCompleteness(profile), [profile]);
    const constituencyChunks = useMemo(() => {
        const perType = brainStats?.per_source_type || {};
        return CONSTITUENCY_SOURCE_TYPES.reduce((sum, sourceType) => sum + (perType[sourceType]?.count || 0), 0);
    }, [brainStats]);
    const profileStatusTone = !profile ? 'red' : completeness.score >= 85 ? 'green' : completeness.score >= 60 ? 'amber' : 'red';
    const indexStatusTone = indexJob.status === 'running' ? 'blue' : constituencyChunks > 0 ? 'green' : 'amber';

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

    async function loadBrainStats(tid = tenantId) {
        if (!tid) {
            setBrainStats(null);
            return;
        }
        try {
            const stats = await apiGet(`/api/admin/brain/stats/${tid}`);
            setBrainStats(stats);
        } catch {
            setBrainStats(null);
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
            setBrainStats(null);
            setGroundingResults(null);
            return;
        }
        loadProfile(selectedSlug).catch(() => show('error', 'Failed to load selected profile.'));
    }, [selectedSlug]);

    useEffect(() => {
        if (!tenantId) return;
        loadBrainStats(tenantId);
        setGroundingQuery((q) => q || `${profile?.meta?.name || ''} water infrastructure`.trim());
    }, [tenantId]);

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

    useEffect(() => {
        if (!indexJob.id || !indexJob.status || indexJob.status === 'done' || indexJob.status === 'error') return;
        const poll = setInterval(async () => {
            try {
                const r = await apiGet(`/api/admin/brain/reindex/status/${indexJob.id}`);
                setIndexJob((j) => ({ ...j, status: r.status, error: r.error || '' }));
                if (r.status === 'done') {
                    clearInterval(poll);
                    await loadBrainStats();
                    show('success', 'Profile indexed. MP frontend grounding can now retrieve it.');
                } else if (r.status === 'error') {
                    clearInterval(poll);
                    show('error', r.error || 'Profile indexing failed.');
                }
            } catch {
                clearInterval(poll);
                show('error', 'Failed to poll indexing job.');
            }
        }, 2500);
        return () => clearInterval(poll);
    }, [indexJob.id, indexJob.status]);

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
                show('success', `PDF parsed and profile saved as "${result.slug}". Review, then index it for MP grounding.`);
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
            show('success', `Saved ${TABS.find((t) => t.key === tab)?.label || 'section'}. Reindex to publish updated grounding.`);
            return true;
        } catch (e) {
            show('error', e.message || 'Failed to save section.');
            return false;
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

    async function reindexProfile() {
        if (!tenantId) {
            show('error', 'This profile is not linked to a tenant.');
            return;
        }
        setBusy(true);
        try {
            const r = await apiPost(`/api/admin/brain/reindex/${tenantId}`, { sources: ['profile'], rebuild: false });
            setIndexJob({ id: r.job_id, status: 'running', error: '' });
            show('success', 'Profile indexing started.');
        } catch (e) {
            show('error', e.message || 'Failed to start profile indexing.');
        } finally {
            setBusy(false);
        }
    }

    async function saveAndReindex() {
        const saved = await saveCurrentSection();
        if (saved) await reindexProfile();
    }

    async function testGrounding() {
        if (!tenantId || !groundingQuery.trim()) return;
        setGroundingBusy(true);
        setGroundingResults(null);
        try {
            const r = await apiPost('/api/admin/brain/retrieve', {
                tenant_id: tenantId,
                query: groundingQuery.trim(),
                source_types: CONSTITUENCY_SOURCE_TYPES,
                include_global: false,
                include_cross_mp: false,
                k: 6,
            });
            setGroundingResults(r.chunks || []);
        } catch (e) {
            show('error', e.message || 'Grounding test failed.');
        } finally {
            setGroundingBusy(false);
        }
    }

    return (
        <div style={{ display: 'grid', gap: 16 }}>
            {msg.text && (
                <div className={`toast ${msg.type === 'success' ? 'toast-success' : 'toast-error'}`}>{msg.text}</div>
            )}

            <div className="glass-panel">
                <div className="section-title">Constituency Knowledge Profiles</div>
                <div style={{ color: '#6b7f76', fontSize: '0.84rem', lineHeight: 1.5, marginBottom: 14 }}>
                    Store constituency background context for AI grounding. Copilot and Drafter retrieve this only when the MP's prompt makes it relevant.
                </div>
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
                        Profile Manager
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
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 10, marginBottom: 14 }}>
                            <ReadinessCard
                                label="Profile Completeness"
                                value={`${completeness.score}%`}
                                detail={`${completeness.done}/${completeness.total} grounding sections present`}
                                tone={profileStatusTone}
                            />
                            <ReadinessCard
                                label="Tenant Link"
                                value={tenantId ? `#${tenantId}` : 'Missing'}
                                detail={selectedProfileMeta?.tenant_name || 'Required before MP frontend can use this profile'}
                                tone={tenantId ? 'green' : 'red'}
                            />
                            <ReadinessCard
                                label="Indexed Chunks"
                                value={indexJob.status === 'running' ? 'Indexing' : constituencyChunks}
                                detail={brainStats?.last_indexed ? `Last indexed ${brainStats.last_indexed.slice(0, 16)}` : 'Run profile indexing after edits'}
                                tone={indexStatusTone}
                            />
                        </div>

                        <div style={{
                            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12,
                            marginBottom: 14,
                        }}>
                            <div style={{ border: '1px solid #e2ebe5', borderRadius: 12, padding: 14, background: '#f8faf9' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center', marginBottom: 10 }}>
                                    <div>
                                        <div style={{ color: '#1a2e28', fontWeight: 850, fontSize: '0.9rem' }}>Readiness Checks</div>
                                        <div style={{ color: '#6b7f76', fontSize: '0.76rem', marginTop: 2 }}>Quick QA before this context reaches MP tools.</div>
                                    </div>
                                    <button className="btn-primary" onClick={reindexProfile} disabled={!tenantId || busy || indexJob.status === 'running'} style={{ whiteSpace: 'nowrap' }}>
                                        {indexJob.status === 'running' ? 'Indexing...' : 'Index Profile'}
                                    </button>
                                </div>
                                <div style={{ display: 'grid', gap: 7 }}>
                                    {completeness.checks.map((c) => (
                                        <div key={c.label} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center' }}>
                                            <div>
                                                <div style={{ color: '#1a2e28', fontSize: '0.78rem', fontWeight: 750 }}>{c.label}</div>
                                                <div style={{ color: '#6b7f76', fontSize: '0.7rem' }}>{c.hint}</div>
                                            </div>
                                            <span className={`badge ${c.done ? 'badge-green' : 'badge-amber'}`} style={{ flexShrink: 0 }}>
                                                {c.done ? 'Ready' : 'Missing'}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div style={{ border: '1px solid #e2ebe5', borderRadius: 12, padding: 14, background: '#f8faf9' }}>
                                <div style={{ color: '#1a2e28', fontWeight: 850, fontSize: '0.9rem' }}>Test Grounding</div>
                                <div style={{ color: '#6b7f76', fontSize: '0.76rem', marginTop: 2, marginBottom: 10 }}>
                                    Simulate whether this profile would be retrieved for an MP prompt.
                                </div>
                                <div style={{ display: 'flex', gap: 8 }}>
                                    <input
                                        className="form-input"
                                        value={groundingQuery}
                                        onChange={(e) => setGroundingQuery(e.target.value)}
                                        placeholder="e.g. water issue, airport upgrade, sugarcane payments"
                                    />
                                    <button className="btn-secondary" onClick={testGrounding} disabled={!tenantId || groundingBusy || !groundingQuery.trim()} style={{ whiteSpace: 'nowrap' }}>
                                        {groundingBusy ? 'Testing...' : 'Test'}
                                    </button>
                                </div>
                                {groundingResults && (
                                    <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
                                        {groundingResults.length === 0 ? (
                                            <div style={{ color: '#d97706', fontSize: '0.8rem' }}>
                                                No constituency chunks matched. Try indexing the profile or use a more local query.
                                            </div>
                                        ) : groundingResults.map((r, i) => (
                                            <div key={r.id || i} style={{ background: '#fff', border: '1px solid #e2ebe5', borderRadius: 9, padding: '9px 10px' }}>
                                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                                                    <div style={{ color: '#1a2e28', fontWeight: 800, fontSize: '0.78rem' }}>{r.title}</div>
                                                    <span style={{ color: '#006a4d', fontSize: '0.72rem', fontWeight: 850 }}>{Math.round((r.score || 0) * 100)}%</span>
                                                </div>
                                                <div style={{ color: '#6b7f76', fontSize: '0.72rem', marginTop: 3 }}>{r.citation}</div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>

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
                                <SectionView tab={tab} profile={profile} />
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
                                    <div style={{ display: 'flex', gap: 8 }}>
                                        <button className="btn-secondary" onClick={saveCurrentSection} disabled={busy || !selectedSlug}>
                                            Save Section
                                        </button>
                                        <button className="btn-primary" onClick={saveAndReindex} disabled={busy || !selectedSlug || !tenantId}>
                                            Save & Index
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
