'use client';
import { useState, useEffect } from 'react';
import { apiGet, apiPatch, apiDelete } from '@/lib/api';

export default function ProfileEditorPage() {
    const [mps, setMps] = useState([]);
    const [selected, setSelected] = useState(null);
    const [profile, setProfile] = useState(null);
    const [constituencies, setConstituencies] = useState([]);
    const [identityForm, setIdentityForm] = useState({});
    const [profileForm, setProfileForm] = useState({});
    const [newPassword, setNewPassword] = useState('');
    const [deleteConfirm, setDeleteConfirm] = useState('');
    const [msg, setMsg] = useState({ type: '', text: '' });

    useEffect(() => {
        apiGet('/api/admin/mps').then(r => setMps(r.mps || [])).catch(() => { });
        apiGet('/api/admin/constituencies').then(r => setConstituencies(r.constituencies || [])).catch(() => { });
    }, []);

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
        }).catch(() => { });
    }, [selected]);

    const completeness = (() => {
        if (!profile || !profile.exists) return 0;
        let score = 0;
        if (identityForm.mp_name) score++;
        if (identityForm.constituency) score++;
        if (identityForm.state) score++;
        if (identityForm.party) score++;
        const facts = profileForm.key_facts?.split('\n').filter(Boolean) || [];
        if (facts.length) score++;
        const langs = profileForm.languages?.split(',').map(s => s.trim()).filter(Boolean) || [];
        if (langs.length > 1) score++;
        const alts = profileForm.alt_names?.split(',').map(s => s.trim()).filter(Boolean) || [];
        if (alts.length) score++;
        if (profileForm.sovereignty_rules) score++;
        return Math.round((score / 8) * 100);
    })();

    const fillClass = completeness >= 70 ? 'fill-good' : completeness >= 40 ? 'fill-mid' : 'fill-low';

    const saveIdentity = async () => {
        setMsg({});
        try {
            const langs = profileForm.languages?.split(',').map(s => s.trim()).filter(Boolean) || ['English', 'Hindi'];
            const facts = profileForm.key_facts?.split('\n').map(s => s.trim()).filter(Boolean) || [];
            const alts = profileForm.alt_names?.split(',').map(s => s.trim()).filter(Boolean) || [];
            await apiPatch(`/api/admin/mps/${selected.tenant_id}/profile`, {
                ...identityForm,
                key_facts: facts, languages: langs, alt_names: alts,
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
            setMsg({ type: 'success', text: 'Identity saved' });
        } catch (err) { setMsg({ type: 'error', text: err.message }); }
    };

    const saveProfileData = async () => {
        setMsg({});
        try {
            const langs = profileForm.languages?.split(',').map(s => s.trim()).filter(Boolean) || ['English', 'Hindi'];
            const facts = profileForm.key_facts?.split('\n').map(s => s.trim()).filter(Boolean) || [];
            const alts = profileForm.alt_names?.split(',').map(s => s.trim()).filter(Boolean) || [];
            await apiPatch(`/api/admin/mps/${selected.tenant_id}/profile`, {
                ...identityForm,
                key_facts: facts, languages: langs, alt_names: alts,
                sovereignty_rules: profileForm.sovereignty_rules || '',
                vocabulary_guide: profile?.vocabulary_guide || {},
            });
            setMsg({ type: 'success', text: 'Profile data saved' });
        } catch (err) { setMsg({ type: 'error', text: err.message }); }
    };

    const handleDelete = async () => {
        if (deleteConfirm !== selected.username) {
            setMsg({ type: 'error', text: "Username doesn't match" });
            return;
        }
        try {
            await apiDelete(`/api/admin/mps/${selected.tenant_id}`);
            setMsg({ type: 'success', text: 'Deleted successfully' });
            setSelected(null);
            setProfile(null);
            apiGet('/api/admin/mps').then(r => setMps(r.mps || [])).catch(() => { });
        } catch (err) { setMsg({ type: 'error', text: err.message }); }
    };

    const mpList = mps.filter(m => m.role !== 'admin' && m.role !== 'super_admin' && m.role !== 'sysadmin');

    return (
        <>
            <div className="section-title">Profile Editor</div>

            {mpList.length === 0 ? (
                <div className="glass-panel" style={{ textAlign: 'center', color: '#6b7f76', padding: '2rem' }}>No MPs registered. Create one first.</div>
            ) : (
                <>
                    <div style={{ marginBottom: '1.5rem' }}>
                        <label className="form-label">Select MP to Edit</label>
                        <select className="form-input" value={selected?.user_id || ''} onChange={(e) => {
                            const mp = mpList.find(m => m.user_id === Number(e.target.value));
                            setSelected(mp || null);
                        }}>
                            <option value="">Choose an MP...</option>
                            {mpList.map(m => <option key={m.user_id} value={m.user_id}>{m.display_name} (@{m.username})</option>)}
                        </select>
                    </div>

                    {selected && profile && (
                        <>
                            {/* Completeness Header */}
                            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
                                <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 8 }}>
                                    Profile: {selected.display_name}
                                </h3>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                    <div style={{ flex: 1 }}>
                                        <div className="completeness-bar" style={{ height: 8 }}>
                                            <div className={`completeness-fill ${fillClass}`} style={{ width: `${completeness}%` }} />
                                        </div>
                                    </div>
                                    <span style={{
                                        color: completeness >= 70 ? '#34d399' : completeness >= 40 ? '#fbbf24' : '#f87171',
                                        fontWeight: 700, fontSize: '0.9rem',
                                    }}>{completeness}%</span>
                                </div>
                            </div>

                            {msg.text && (
                                <div style={{
                                    background: msg.type === 'success' ? 'rgba(5,150,105,0.06)' : 'rgba(220,38,38,0.06)',
                                    border: `1px solid ${msg.type === 'success' ? 'rgba(5,150,105,0.15)' : 'rgba(220,38,38,0.15)'}`,
                                    color: msg.type === 'success' ? '#059669' : '#dc2626',
                                    padding: '10px 14px', borderRadius: 10, fontSize: '0.82rem', marginBottom: '1rem',
                                }}>{msg.text}</div>
                            )}

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
                                {/* Left: Identity */}
                                <div className="glass-panel">
                                    <div className="section-title">Identity & Credentials</div>
                                    <div style={{ marginBottom: 12 }}>
                                        <label className="form-label">MP Name</label>
                                        <input className="form-input" value={identityForm.mp_name || ''} onChange={e => setIdentityForm({ ...identityForm, mp_name: e.target.value })} />
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
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
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
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
                                    <hr style={{ border: 'none', borderTop: '1px solid #e2ebe5', margin: '16px 0' }} />
                                    <div style={{ marginBottom: 12 }}>
                                        <label className="form-label">Reset Password (leave blank to keep current)</label>
                                        <input className="form-input" type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="New password" />
                                    </div>
                                    <button type="button" className="btn-primary" onClick={saveIdentity} style={{ width: '100%' }}>Save Identity</button>
                                </div>

                                {/* Right: Profile Data */}
                                <div className="glass-panel">
                                    <div className="section-title">News & Drafter Profile</div>
                                    <div style={{ marginBottom: 12 }}>
                                        <label className="form-label">Languages (comma-separated)</label>
                                        <input className="form-input" value={profileForm.languages || ''} onChange={e => setProfileForm({ ...profileForm, languages: e.target.value })} />
                                    </div>
                                    <div style={{ marginBottom: 12 }}>
                                        <label className="form-label">Key Facts (one per line)</label>
                                        <textarea className="form-input" rows={5} value={profileForm.key_facts || ''} onChange={e => setProfileForm({ ...profileForm, key_facts: e.target.value })} />
                                    </div>
                                    <div style={{ marginBottom: 12 }}>
                                        <label className="form-label">Alt Constituency Names (comma-separated)</label>
                                        <input className="form-input" value={profileForm.alt_names || ''} onChange={e => setProfileForm({ ...profileForm, alt_names: e.target.value })} />
                                    </div>
                                    <div style={{ marginBottom: 12 }}>
                                        <label className="form-label">Sovereignty Rules</label>
                                        <textarea className="form-input" rows={3} value={profileForm.sovereignty_rules || ''} onChange={e => setProfileForm({ ...profileForm, sovereignty_rules: e.target.value })} placeholder="Special rules for the AI drafter (e.g. border stance)" />
                                    </div>
                                    <button type="button" className="btn-primary" onClick={saveProfileData} style={{ width: '100%' }}>Save Profile Data</button>
                                </div>
                            </div>

                            {/* Danger Zone */}
                            <div className="glass-panel" style={{ marginTop: '1.5rem', borderColor: 'rgba(220,38,38,0.2)' }}>
                                <div style={{ color: '#dc2626', fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '1.2px', marginBottom: 12 }}>Danger Zone</div>
                                <p style={{ color: '#6b7f76', fontSize: '0.85rem', marginBottom: 12 }}>
                                    Permanently delete <strong>{selected.display_name}</strong> and all their data?
                                </p>
                                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                                    <input className="form-input" style={{ flex: 1 }} placeholder={`Type "${selected.username}" to confirm`} value={deleteConfirm} onChange={e => setDeleteConfirm(e.target.value)} />
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
