'use client';
import { useState, useEffect } from 'react';
import { apiGet, apiPatch, apiPost, apiDelete } from '@/lib/api';

export default function SettingsPage() {
    const [editors, setEditors] = useState([]);
    const [pwForm, setPwForm] = useState({ current: '', new_pw: '', confirm: '' });
    const [edForm, setEdForm] = useState({ username: '', display_name: '', password: '' });
    const [msg, setMsg] = useState({ type: '', text: '' });
    const [edMsg, setEdMsg] = useState({ type: '', text: '' });

    useEffect(() => {
        apiGet('/api/admin/editors').then(r => setEditors(r.editors || [])).catch(() => { });
    }, []);

    const showMsg = (setter, type, text) => {
        setter({ type, text });
        setTimeout(() => setter({ type: '', text: '' }), 4000);
    };

    const handlePasswordReset = async () => {
        if (!pwForm.current || !pwForm.new_pw) { showMsg(setMsg, 'error', 'Fill all fields'); return; }
        if (pwForm.new_pw !== pwForm.confirm) { showMsg(setMsg, 'error', "Passwords don't match"); return; }
        try {
            await apiPatch('/api/admin/settings/password', { current_password: pwForm.current, new_password: pwForm.new_pw });
            showMsg(setMsg, 'success', 'Admin password updated');
            setPwForm({ current: '', new_pw: '', confirm: '' });
        } catch (err) { showMsg(setMsg, 'error', err.message); }
    };

    const handleCreateEditor = async () => {
        if (!edForm.username || !edForm.password) { showMsg(setEdMsg, 'error', 'Username and password required'); return; }
        try {
            await apiPost('/api/admin/editors', { username: edForm.username, password: edForm.password, display_name: edForm.display_name });
            showMsg(setEdMsg, 'success', `Editor '${edForm.username}' created`);
            setEdForm({ username: '', display_name: '', password: '' });
            apiGet('/api/admin/editors').then(r => setEditors(r.editors || [])).catch(() => { });
        } catch (err) { showMsg(setEdMsg, 'error', err.message); }
    };

    const handleDeleteEditor = async (id) => {
        try {
            await apiDelete(`/api/admin/editors/${id}`);
            setEditors(editors.filter(e => e.id !== id));
        } catch { }
    };

    return (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {/* Admin Password Reset */}
            <div className="glass-panel">
                <div style={{ fontWeight: 700, color: '#1a2e28', fontSize: '0.95rem', marginBottom: '1.25rem' }}>
                    Reset Admin Password
                </div>
                <div className="form-row">
                    <label className="form-label">Current Password</label>
                    <input className="form-input" type="password" value={pwForm.current} onChange={e => setPwForm({ ...pwForm, current: e.target.value })} />
                </div>
                <div className="form-row">
                    <label className="form-label">New Password</label>
                    <input className="form-input" type="password" value={pwForm.new_pw} onChange={e => setPwForm({ ...pwForm, new_pw: e.target.value })} />
                </div>
                <div className="form-row">
                    <label className="form-label">Confirm New Password</label>
                    <input className="form-input" type="password" value={pwForm.confirm} onChange={e => setPwForm({ ...pwForm, confirm: e.target.value })} />
                </div>
                {msg.text && <div className={`toast ${msg.type === 'success' ? 'toast-success' : 'toast-error'}`}>{msg.text}</div>}
                <button className="btn-primary" onClick={handlePasswordReset} style={{ width: '100%' }}>
                    Update Password
                </button>
            </div>

            {/* Editor Management */}
            <div className="glass-panel">
                <div style={{ fontWeight: 700, color: '#1a2e28', fontSize: '0.95rem', marginBottom: 4 }}>
                    Editors <span style={{ fontSize: '0.72rem', fontWeight: 400, color: '#6b7f76', marginLeft: 4 }}>(Restricted Access)</span>
                </div>
                <p style={{ color: '#6b7f76', fontSize: '0.78rem', marginBottom: '1.25rem', marginTop: 4 }}>
                    Editors can view MP data and geography but cannot create or delete MPs.
                </p>

                <div className="form-row">
                    <label className="form-label">Editor Username *</label>
                    <input className="form-input" placeholder="editor_name" value={edForm.username} onChange={e => setEdForm({ ...edForm, username: e.target.value })} />
                </div>
                <div className="form-row">
                    <label className="form-label">Display Name</label>
                    <input className="form-input" placeholder="Editor display name" value={edForm.display_name} onChange={e => setEdForm({ ...edForm, display_name: e.target.value })} />
                </div>
                <div className="form-row">
                    <label className="form-label">Password *</label>
                    <input className="form-input" type="password" value={edForm.password} onChange={e => setEdForm({ ...edForm, password: e.target.value })} />
                </div>
                {edMsg.text && <div className={`toast ${edMsg.type === 'success' ? 'toast-success' : 'toast-error'}`}>{edMsg.text}</div>}
                <button className="btn-primary" onClick={handleCreateEditor} style={{ width: '100%', marginBottom: '1.25rem' }}>
                    Create Editor
                </button>

                {editors.length > 0 && (
                    <>
                        <hr className="divider" />
                        <div style={{ fontSize: '0.76rem', color: '#6b7f76', marginBottom: 10 }}>
                            <strong style={{ color: '#1a2e28' }}>{editors.length}</strong> editor{editors.length !== 1 ? 's' : ''}
                        </div>
                        {editors.map(ed => (
                            <div key={ed.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '9px 0', borderBottom: '1px solid #f0f4f1' }}>
                                <div>
                                    <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#1a2e28' }}>{ed.display_name}</span>
                                    <span style={{ color: '#6b7f76', fontSize: '0.76rem', marginLeft: 8 }}>@{ed.username}</span>
                                </div>
                                <button className="btn-danger" style={{ fontSize: '0.72rem', padding: '4px 10px' }} onClick={() => handleDeleteEditor(ed.id)}>
                                    Remove
                                </button>
                            </div>
                        ))}
                    </>
                )}
                {editors.length === 0 && (
                    <div style={{ color: '#6b7f76', fontSize: '0.82rem', textAlign: 'center', padding: '1rem', background: '#f8faf9', borderRadius: 8 }}>
                        No editors created yet
                    </div>
                )}
            </div>
        </div>
    );
}
