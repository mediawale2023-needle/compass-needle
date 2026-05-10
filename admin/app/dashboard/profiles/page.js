'use client';
import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { apiGet, apiPatch, apiDelete, apiPost } from '@/lib/api';

export default function ProfileEditorPage() {
    const searchParams = useSearchParams();
    const requestedTenantId = searchParams.get('tenant_id');
    const [mps, setMps] = useState([]);
    const [selected, setSelected] = useState(null);
    const [profile, setProfile] = useState(null);
    const [constituencies, setConstituencies] = useState([]);
    const [identityForm, setIdentityForm] = useState({});
    const [profileForm, setProfileForm] = useState({});
    const [waForm, setWaForm] = useState({ whatsapp_number: '', phone_number_id: '' });
    const [newPassword, setNewPassword] = useState('');
    const [deleteConfirm, setDeleteConfirm] = useState('');
    const [msg, setMsg] = useState({ type: '', text: '' });

    // Geography
    const [geoData, setGeoData] = useState({});        // { assembly: [localities] }
    const [geoAssembly, setGeoAssembly] = useState('');
    const [geoLocalities, setGeoLocalities] = useState(''); // textarea, one per line
    const [geoLoading, setGeoLoading] = useState(false);

    useEffect(() => {
        apiGet('/api/admin/mps').then(r => setMps(r.mps || [])).catch(() => { });
        apiGet('/api/admin/constituencies').then(r => setConstituencies(r.constituencies || [])).catch(() => { });
    }, []);

    useEffect(() => {
        if (!requestedTenantId || selected || mps.length === 0) return;
        const mp = mps.find(item => String(item.tenant_id) === String(requestedTenantId));
        if (mp) setSelected(mp);
    }, [requestedTenantId, selected, mps]);

    useEffect(() => {
        if (!selected) return;
        apiGet(`/api/admin/mps/${selected.tenant_id}/profile`).then(p => {
            setProfile(p);
            setIdentityForm({
                mp_name: p.mp_name || selected.display_name,
                constituency: p.constituency || selected.parliamentary_constituency,
                state: p.state || '',
                house: p.house || selected.house,
                party: p.party || 'Independent',
            });
            setProfileForm({
                languages: (p.languages || ['English', 'Hindi']).join(', '),
                key_facts: (p.key_facts || []).join('\n'),
                alt_names: (p.alt_names || []).join(', '),
                sovereignty_rules: p.sovereignty_rules || '',
            });
            setWaForm({
                whatsapp_number: p.whatsapp_number || '',
                phone_number_id: p.phone_number_id || '',
            });
        }).catch(() => { });
        // Load geography data
        apiGet(`/api/admin/mps/${selected.tenant_id}/geography`)
            .then(g => setGeoData(g.assemblies || {}))
            .catch(() => setGeoData({}));
    }, [selected]);

    const completeness = (() => {
        if (!profile || !profile.exists) return 0;
        let score = 0;
        if (identityForm.mp_name) score++;
        if (identityForm.constituency) score++;
        if (identityForm.state) score++;
        if (identityForm.party) score++;
        if (profileForm.key_facts?.split('\n').filter(Boolean).length) score++;
        if (profileForm.languages?.split(',').map(s => s.trim()).filter(Boolean).length > 1) score++;
        if (profileForm.alt_names?.split(',').map(s => s.trim()).filter(Boolean).length) score++;
        if (profileForm.sovereignty_rules) score++;
        return Math.round((score / 8) * 100);
    })();

    const fillClass = completeness >= 70 ? 'fill-good' : completeness >= 40 ? 'fill-mid' : 'fill-low';
    const completenessColor = completeness >= 70 ? '#059669' : completeness >= 40 ? '#d97706' : '#dc2626';

    const showMsg = (type, text) => {
        setMsg({ type, text });
        setTimeout(() => setMsg({ type: '', text: '' }), 4000);
    };

    const saveIdentity = async () => {
        try {
            const langs = profileForm.languages?.split(',').map(s => s.trim()).filter(Boolean) || ['English', 'Hindi'];
            const facts = profileForm.key_facts?.split('\n').map(s => s.trim()).filter(Boolean) || [];
            const alts = profileForm.alt_names?.split(',').map(s => s.trim()).filter(Boolean) || [];
            await apiPatch(`/api/admin/mps/${selected.tenant_id}/profile`, {
                ...identityForm, key_facts: facts, languages: langs, alt_names: alts,
                sovereignty_rules: profileForm.sovereignty_rules || '',
                vocabulary_guide: profile?.vocabulary_guide || {},
            });
            if (identityForm.constituency !== selected.parliamentary_constituency) {
                await apiPatch(`/api/admin/mps/${selected.tenant_id}/constituency`, { constituency: identityForm.constituency });
            }
            if (newPassword) {
                await apiPatch(`/api/admin/mps/${selected.tenant_id}/password`, { new_password: newPassword });
                setNewPassword('');
            }
            showMsg('success', 'Identity saved successfully');
        } catch (err) { showMsg('error', err.message); }
    };

    const saveProfileData = async () => {
        try {
            const langs = profileForm.languages?.split(',').map(s => s.trim()).filter(Boolean) || ['English', 'Hindi'];
            const facts = profileForm.key_facts?.split('\n').map(s => s.trim()).filter(Boolean) || [];
            const alts = profileForm.alt_names?.split(',').map(s => s.trim()).filter(Boolean) || [];
            await apiPatch(`/api/admin/mps/${selected.tenant_id}/profile`, {
                ...identityForm, key_facts: facts, languages: langs, alt_names: alts,
                sovereignty_rules: profileForm.sovereignty_rules || '',
                vocabulary_guide: profile?.vocabulary_guide || {},
            });
            showMsg('success', 'Profile data saved successfully');
        } catch (err) { showMsg('error', err.message); }
    };

    const saveGeo = async () => {
        if (!geoAssembly.trim()) { showMsg('error', 'Assembly constituency name is required'); return; }
        const locs = geoLocalities.split('\n').map(l => l.trim()).filter(Boolean);
        if (!locs.length) { showMsg('error', 'Enter at least one locality'); return; }
        setGeoLoading(true);
        try {
            await apiPost(`/api/admin/mps/${selected.tenant_id}/geography/bulk`, {
                parliamentary_constituency: selected.parliamentary_constituency || identityForm.constituency,
                assembly_constituency: geoAssembly.trim(),
                localities: locs,
            });
            showMsg('success', `Saved ${locs.length} localities for ${geoAssembly}`);
            setGeoAssembly('');
            setGeoLocalities('');
            const g = await apiGet(`/api/admin/mps/${selected.tenant_id}/geography`);
            setGeoData(g.assemblies || {});
        } catch (err) { showMsg('error', err.message); }
        finally { setGeoLoading(false); }
    };

    const deleteGeoAssembly = async (assembly) => {
        if (!confirm(`Delete all localities for "${assembly}"?`)) return;
        try {
            await apiDelete(`/api/admin/mps/${selected.tenant_id}/geography/${encodeURIComponent(assembly)}`);
            showMsg('success', `Deleted ${assembly}`);
            const g = await apiGet(`/api/admin/mps/${selected.tenant_id}/geography`);
            setGeoData(g.assemblies || {});
        } catch (err) { showMsg('error', err.message); }
    };

    const saveWhatsApp = async () => {
        if (!waForm.whatsapp_number.startsWith('+')) {
            showMsg('error', "WhatsApp number must start with + and include country code (e.g. +919289372849)");
            return;
        }
        try {
            await apiPatch(`/api/admin/mps/${selected.tenant_id}/whatsapp`, {
                whatsapp_number: waForm.whatsapp_number,
                phone_number_id: waForm.phone_number_id || '',
            });
            showMsg('success', 'WhatsApp configuration saved');
        } catch (err) { showMsg('error', err.message); }
    };

    const handleDelete = async () => {
        if (deleteConfirm !== selected.username) {
            showMsg('error', "Username doesn't match");
            return;
        }
        try {
            await apiDelete(`/api/admin/mps/${selected.tenant_id}`);
            showMsg('success', 'Deleted successfully');
            setSelected(null);
            setProfile(null);
            apiGet('/api/admin/mps').then(r => setMps(r.mps || [])).catch(() => { });
        } catch (err) { showMsg('error', err.message); }
    };

    const mpList = mps.filter(m => m.role !== 'admin' && m.role !== 'super_admin' && m.role !== 'sysadmin');

    return (
        <>
            {mpList.length === 0 ? (
                <div className="glass-panel">
                    <div className="empty-state">
                        <div className="empty-state-title">No MPs registered</div>
                        <div className="empty-state-desc">Create an MP account first from the Overview page</div>
                    </div>
                </div>
            ) : (
                <>
                    <div className="form-row">
                        <label className="form-label">Select MP to Edit</label>
                        <select className="form-input" value={selected?.user_id || ''} onChange={(e) => {
                            const mp = mpList.find(m => m.user_id === Number(e.target.value));
                            setSelected(mp || null);
                            setMsg({});
                        }}>
                            <option value="">Choose an MP…</option>
                            {mpList.map(m => <option key={m.user_id} value={m.user_id}>{m.display_name} (@{m.username})</option>)}
                        </select>
                    </div>

                    {selected && profile && (
                        <>
                            {/* Completeness Bar */}
                            <div className="glass-panel" style={{ marginBottom: '1.25rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                                    <div style={{ fontWeight: 600, color: '#1a2e28', fontSize: '0.9rem' }}>
                                        {selected.display_name}
                                    </div>
                                    <span style={{ fontWeight: 700, fontSize: '0.88rem', color: completenessColor }}>
                                        {completeness}% complete
                                    </span>
                                </div>
                                <div className="completeness-bar" style={{ height: 7 }}>
                                    <div className={`completeness-fill ${fillClass}`} style={{ width: `${completeness}%` }} />
                                </div>
                            </div>

                            {msg.text && (
                                <div className={`toast ${msg.type === 'success' ? 'toast-success' : 'toast-error'}`}>
                                    {msg.text}
                                </div>
                            )}

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: '1.25rem' }}>
                                {/* Identity */}
                                <div className="glass-panel">
                                    <div className="section-title">Identity & Credentials</div>
                                    <div className="form-row">
                                        <label className="form-label">MP Name</label>
                                        <input className="form-input" value={identityForm.mp_name || ''} onChange={e => setIdentityForm({ ...identityForm, mp_name: e.target.value })} />
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                                        <div>
                                            <label className="form-label">Constituency</label>
                                            {selected.house === 'Lok Sabha' ? (
                                                <select className="form-input" value={identityForm.constituency || ''} onChange={e => setIdentityForm({ ...identityForm, constituency: e.target.value })}>
                                                    {constituencies.map(c => <option key={c} value={c}>{c}</option>)}
                                                </select>
                                            ) : (
                                                <input className="form-input" value={identityForm.constituency || ''} onChange={e => setIdentityForm({ ...identityForm, constituency: e.target.value })} />
                                            )}
                                        </div>
                                        <div>
                                            <label className="form-label">State</label>
                                            <input className="form-input" value={identityForm.state || ''} onChange={e => setIdentityForm({ ...identityForm, state: e.target.value })} />
                                        </div>
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                                        <div>
                                            <label className="form-label">House</label>
                                            <select className="form-input" value={identityForm.house || 'Lok Sabha'} onChange={e => setIdentityForm({ ...identityForm, house: e.target.value })}>
                                                <option value="Lok Sabha">Lok Sabha</option>
                                                <option value="Rajya Sabha">Rajya Sabha</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label className="form-label">Party</label>
                                            <input className="form-input" value={identityForm.party || ''} onChange={e => setIdentityForm({ ...identityForm, party: e.target.value })} />
                                        </div>
                                    </div>
                                    <hr className="divider" />
                                    <div className="form-row">
                                        <label className="form-label">Reset Password <span style={{ fontWeight: 400, color: '#94a3b8' }}>(leave blank to keep current)</span></label>
                                        <input className="form-input" type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="New password" />
                                    </div>
                                    <button type="button" className="btn-primary" onClick={saveIdentity} style={{ width: '100%' }}>
                                        Save Identity
                                    </button>
                                </div>

                                {/* Profile Data */}
                                <div className="glass-panel">
                                    <div className="section-title">News & Drafter Profile</div>
                                    <div className="form-row">
                                        <label className="form-label">Languages <span style={{ fontWeight: 400, color: '#94a3b8' }}>(comma-separated)</span></label>
                                        <input className="form-input" value={profileForm.languages || ''} onChange={e => setProfileForm({ ...profileForm, languages: e.target.value })} />
                                    </div>
                                    <div className="form-row">
                                        <label className="form-label">Key Facts <span style={{ fontWeight: 400, color: '#94a3b8' }}>(one per line)</span></label>
                                        <textarea className="form-input" rows={5} value={profileForm.key_facts || ''} onChange={e => setProfileForm({ ...profileForm, key_facts: e.target.value })} />
                                    </div>
                                    <div className="form-row">
                                        <label className="form-label">Alt Constituency Names <span style={{ fontWeight: 400, color: '#94a3b8' }}>(comma-separated)</span></label>
                                        <input className="form-input" value={profileForm.alt_names || ''} onChange={e => setProfileForm({ ...profileForm, alt_names: e.target.value })} />
                                    </div>
                                    <div className="form-row">
                                        <label className="form-label">Sovereignty Rules</label>
                                        <textarea className="form-input" rows={3} value={profileForm.sovereignty_rules || ''} onChange={e => setProfileForm({ ...profileForm, sovereignty_rules: e.target.value })} placeholder="Special rules for the AI drafter (e.g. border stance)" />
                                    </div>
                                    <button type="button" className="btn-primary" onClick={saveProfileData} style={{ width: '100%' }}>
                                        Save Profile Data
                                    </button>
                                </div>
                            </div>

                            {/* WhatsApp Configuration */}
                            <div className="glass-panel" style={{ marginBottom: '1.25rem' }}>
                                <div className="section-title">WhatsApp Configuration</div>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
                                    <div>
                                        <label className="form-label">WhatsApp Number <span style={{ fontWeight: 400, color: '#94a3b8' }}>(+country code)</span></label>
                                        <input
                                            className="form-input"
                                            value={waForm.whatsapp_number}
                                            onChange={e => setWaForm({ ...waForm, whatsapp_number: e.target.value })}
                                            placeholder="+919289372849"
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Meta Phone Number ID</label>
                                        <input
                                            className="form-input"
                                            value={waForm.phone_number_id}
                                            onChange={e => setWaForm({ ...waForm, phone_number_id: e.target.value })}
                                            placeholder="e.g. 1089911394213487"
                                        />
                                    </div>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                    <button type="button" className="btn-primary" onClick={saveWhatsApp}>
                                        Save WhatsApp Config
                                    </button>
                                    {waForm.whatsapp_number && (
                                        <span style={{ fontSize: '0.8rem', color: waForm.phone_number_id ? '#059669' : '#d97706' }}>
                                            {waForm.phone_number_id ? '✓ Phone Number ID set' : '⚠ Phone Number ID not set (will use global fallback)'}
                                        </span>
                                    )}
                                </div>
                            </div>

                            {/* Constituency Geography */}
                            <div className="glass-panel" style={{ marginBottom: '1.25rem' }}>
                                <div className="section-title">Constituency Geography</div>
                                <p style={{ fontSize: '0.82rem', color: '#6b7f76', marginBottom: 14, marginTop: 0 }}>
                                    Location → Assembly Constituency mappings. Stored in the database — survives all redeployments.
                                    Add each assembly segment's localities so WhatsApp complaints are routed correctly.
                                </p>

                                {/* Existing assemblies */}
                                {Object.keys(geoData).length > 0 && (
                                    <div style={{ marginBottom: 16 }}>
                                        {Object.entries(geoData).map(([assembly, locs]) => (
                                            <div key={assembly} style={{ background: '#f0f7f4', borderRadius: 8, padding: '10px 14px', marginBottom: 8, display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                                                <div style={{ flex: 1 }}>
                                                    <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#1a2e28', marginBottom: 4 }}>{assembly}</div>
                                                    <div style={{ fontSize: '0.78rem', color: '#6b7f76', lineHeight: 1.6 }}>
                                                        {locs.slice(0, 8).join(' · ')}{locs.length > 8 ? ` +${locs.length - 8} more` : ''}
                                                    </div>
                                                </div>
                                                <button
                                                    onClick={() => { setGeoAssembly(assembly); setGeoLocalities(locs.join('\n')); }}
                                                    style={{ fontSize: '0.75rem', color: '#059669', background: 'none', border: 'none', cursor: 'pointer', padding: '4px 8px', borderRadius: 4, whiteSpace: 'nowrap' }}>
                                                    Edit
                                                </button>
                                                <button
                                                    onClick={() => deleteGeoAssembly(assembly)}
                                                    style={{ fontSize: '0.75rem', color: '#dc2626', background: 'none', border: 'none', cursor: 'pointer', padding: '4px 8px', borderRadius: 4 }}>
                                                    ✕
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* Add / Edit form */}
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12, marginBottom: 12 }}>
                                    <div>
                                        <label className="form-label">Assembly Constituency Name</label>
                                        <input
                                            className="form-input"
                                            value={geoAssembly}
                                            onChange={e => setGeoAssembly(e.target.value)}
                                            placeholder="e.g. Koil"
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Localities <span style={{ fontWeight: 400, color: '#94a3b8' }}>(one per line — village, mohalla, road, landmark)</span></label>
                                        <textarea
                                            className="form-input"
                                            rows={5}
                                            value={geoLocalities}
                                            onChange={e => setGeoLocalities(e.target.value)}
                                            placeholder={"GT Road\nCivil Lines\nSasni Gate\nQuarsi\nDelhi Gate"}
                                        />
                                    </div>
                                </div>
                                <button type="button" className="btn-primary" onClick={saveGeo} disabled={geoLoading}>
                                    {geoLoading ? 'Saving…' : `Save ${geoAssembly ? `"${geoAssembly}"` : 'Assembly'} Localities`}
                                </button>
                            </div>

                            {/* Danger Zone */}
                            <div className="danger-zone">
                                <div className="danger-zone-label">Danger Zone</div>
                                <p style={{ color: '#6b7f76', fontSize: '0.84rem', marginBottom: 14, marginTop: 0 }}>
                                    Permanently delete <strong style={{ color: '#1a2e28' }}>{selected.display_name}</strong> and all their data. This cannot be undone.
                                </p>
                                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                                    <input
                                        className="form-input"
                                        style={{ flex: 1 }}
                                        placeholder={`Type "${selected.username}" to confirm`}
                                        value={deleteConfirm}
                                        onChange={e => setDeleteConfirm(e.target.value)}
                                    />
                                    <button className="btn-danger" onClick={handleDelete}>Delete MP</button>
                                </div>
                            </div>
                        </>
                    )}
                </>
            )}
        </>
    );
}
