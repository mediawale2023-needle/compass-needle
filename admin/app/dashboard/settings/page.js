'use client';
import { useState, useEffect } from 'react';
import { apiGet, apiPatch, apiPost, apiDelete } from '@/lib/api';
import { useAuth } from '@/lib/auth';

export default function SettingsPage() {
    const { user } = useAuth();
    const [editors, setEditors] = useState([]);
    const [pwForm, setPwForm] = useState({ current: '', new_pw: '', confirm: '' });
    const [edForm, setEdForm] = useState({ username: '', display_name: '', password: '' });
    const [msg, setMsg] = useState({ type: '', text: '' });
    const [edMsg, setEdMsg] = useState({ type: '', text: '' });

    useEffect(() => {
        apiGet('/api/admin/editors').then(r => setEditors(r.editors || [])).catch(() => { });
    }, []);

    const handlePasswordReset = async () => {
        setMsg({});
        if (!pwForm.current || !pwForm.new_pw) {
            setMsg({ type: 'error', text: 'Fill all fields' });
            return;
        }
        if (pwForm.new_pw !== pwForm.confirm) {
            setMsg({ type: 'error', text: "Passwords don't match" });
            return;
        }
        try {
            await apiPatch('/api/admin/settings/password', {
                current_password: pwForm.current,
                new_password: pwForm.new_pw,
            });
            setMsg({ type: 'success', text: 'Admin password updated' });
            setPwForm({ current: '', new_pw: '', confirm: '' });
        } catch (err) {
            setMsg({ type: 'error', text: err.message });
        }
    };

    const handleCreateEditor = async () => {
        setEdMsg({});
        if (!edForm.username || !edForm.password) {
            setEdMsg({ type: 'error', text: 'Username and password required' });
            return;
        }
        try {
            await apiPost('/api/admin/editors', {
                username: edForm.username,
                password: edForm.password,
                display_name: edForm.display_name,
            });
            setEdMsg({ type: 'success', text: `Editor '${edForm.username}' created` });
            setEdForm({ username: '', display_name: '', password: '' });
            apiGet('/api/admin/editors').then(r => setEditors(r.editors || [])).catch(() => { });
        } catch (err) {
            setEdMsg({ type: 'error', text: err.message });
        }
    };

    const handleDeleteEditor = async (id) => {
        try {
            await apiDelete(`/api/admin/editors/${id}`);
            setEditors(editors.filter(e => e.id !== id));
        } catch { }
    };

    return (
        <>
            <div className="section-title">Settings</div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
                {/* Admin Password Reset */}
                <div className="glass-panel">
                    <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Reset Admin Password</h3>
                    <div style={{ marginBottom: 12 }}>
                        <label className="form-label">Current Password</label>
                        <input className="form-input" type="password" value={pwForm.current} onChange={e => setPwForm({ ...pwForm, current: e.target.value })} />
                    </div>
                    <div style={{ marginBottom: 12 }}>
                        <label className="form-label">New Password</label>
                        <input className="form-input" type="password" value={pwForm.new_pw} onChange={e => setPwForm({ ...pwForm, new_pw: e.target.value })} />
                    </div>
                    <div style={{ marginBottom: 12 }}>
                        <label className="form-label">Confirm New Password</label>
                        <input className="form-input" type="password" value={pwForm.confirm} onChange={e => setPwForm({ ...pwForm, confirm: e.target.value })} />
                    </div>
                    {msg.text && (
                        <div style={{
                            background: msg.type === 'success' ? 'rgba(5,150,105,0.06)' : 'rgba(220,38,38,0.06)',
                            border: `1px solid ${msg.type === 'success' ? 'rgba(5,150,105,0.15)' : 'rgba(220,38,38,0.15)'}`,
                            color: msg.type === 'success' ? '#059669' : '#dc2626',
                            padding: '10px 14px', borderRadius: 10, fontSize: '0.82rem', marginBottom: 12,
                        }}>{msg.text}</div>
                    )}
                    <button className="btn-primary" onClick={handlePasswordReset} style={{ width: '100%' }}>Update Password</button>
                </div>

                {/* Editor Management */}
                <div className="glass-panel">
                    <h3 style={{ color: '#1a2e28', fontSize: '1rem', fontWeight: 600, marginBottom: 4 }}>Editors (Restricted Access)</h3>
                    <p style={{ color: '#6b7f76', fontSize: '0.78rem', marginBottom: '1rem' }}>
                        Editors can view MP data and geography but cannot create/delete MPs or change settings.
                    </p>

                    {/* Create Editor Form */}
                    <div style={{ marginBottom: 12 }}>
                        <label className="form-label">Editor Username *</label>
                        <input className="form-input" placeholder="editor_name" value={edForm.username} onChange={e => setEdForm({ ...edForm, username: e.target.value })} />
                    </div>
                    <div style={{ marginBottom: 12 }}>
                        <label className="form-label">Display Name</label>
                        <input className="form-input" placeholder="Editor display name" value={edForm.display_name} onChange={e => setEdForm({ ...edForm, display_name: e.target.value })} />
                    </div>
                    <div style={{ marginBottom: 12 }}>
                        <label className="form-label">Password *</label>
                        <input className="form-input" type="password" value={edForm.password} onChange={e => setEdForm({ ...edForm, password: e.target.value })} />
                    </div>
                    {edMsg.text && (
                        <div style={{
                            background: edMsg.type === 'success' ? 'rgba(5,150,105,0.06)' : 'rgba(220,38,38,0.06)',
                            border: `1px solid ${edMsg.type === 'success' ? 'rgba(5,150,105,0.15)' : 'rgba(220,38,38,0.15)'}`,
                            color: edMsg.type === 'success' ? '#059669' : '#dc2626',
                            padding: '10px 14px', borderRadius: 10, fontSize: '0.82rem', marginBottom: 12,
                        }}>{edMsg.text}</div>
                    )}
                    <button className="btn-primary" onClick={handleCreateEditor} style={{ width: '100%', marginBottom: '1rem' }}>Create Editor</button>

                    {/* Editor List */}
                    {editors.length > 0 ? (
                        <>
                            <hr style={{ border: 'none', borderTop: '1px solid #e2ebe5', margin: '12px 0' }} />
                            <div style={{ fontSize: '0.82rem', fontWeight: 500, color: '#6b7f76', marginBottom: 12 }}>
                                <strong>{editors.length}</strong> editor(s)
                            </div>
                            {editors.map(ed => (
                                <div key={ed.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f0f4f1' }}>
                                    <div>
                                        <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{ed.display_name}</span>
                                        <span style={{ color: '#6b7f76', fontSize: '0.78rem', marginLeft: 8 }}>@{ed.username}</span>
                                    </div>
                                    <button className="btn-danger" style={{ fontSize: '0.72rem', padding: '4px 10px' }} onClick={() => handleDeleteEditor(ed.id)}>Remove</button>
                                </div>
                            ))}
                        </>
                    ) : (
                        <div style={{ color: '#6b7f76', fontSize: '0.82rem', textAlign: 'center', padding: '1rem' }}>
                            No editors created yet.
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}
