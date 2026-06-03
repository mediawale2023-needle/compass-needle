'use client';
import { useState, useEffect } from 'react';
import { apiGet, apiPost, apiPatch } from '@/lib/api';
import ConfirmModal from '@/components/ConfirmModal';

const ROLE_COLORS = { manager: 'badge-purple', staff: 'badge-blue', user: 'badge-slate', mp: 'badge-green', pr: 'badge-blue' };

const BLANK_CREATE = { tenant_id: '', username: '', password: '', display_name: '', role: 'staff', phone: '' };

export default function StaffManagementPage() {
    const [staff, setStaff] = useState([]);
    const [mps, setMps] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [search, setSearch] = useState('');
    const [editing, setEditing] = useState(null);
    const [reassigning, setReassigning] = useState(null);
    const [creating, setCreating] = useState(false);
    const [createForm, setCreateForm] = useState(BLANK_CREATE);
    const [saving, setSaving] = useState(false);
    const [actionMsg, setActionMsg] = useState({ type: '', text: '' });
    const [suspendTarget, setSuspendTarget] = useState(null);

    const loadData = () =>
        Promise.all([apiGet('/api/admin/staff'), apiGet('/api/admin/mps')])
            .then(([s, m]) => { setStaff(s.staff || []); setMps(m.mps || []); })
            .catch(e => setError(e.message || 'Failed to load'))
            .finally(() => setLoading(false));

    useEffect(() => { loadData(); }, []);

    const filtered = search
        ? staff.filter(s =>
            (s.display_name || '').toLowerCase().includes(search.toLowerCase()) ||
            (s.username || '').toLowerCase().includes(search.toLowerCase()) ||
            (s.constituency || '').toLowerCase().includes(search.toLowerCase()) ||
            (s.tenant_name || '').toLowerCase().includes(search.toLowerCase())
        )
        : staff;

    const showMsg = (type, text) => { setActionMsg({ type, text }); setTimeout(() => setActionMsg({ type: '', text: '' }), 3500); };

    const handleSuspend = (member) => setSuspendTarget(member);

    const confirmSuspend = async () => {
        if (!suspendTarget) return;
        const member = suspendTarget;
        setSuspendTarget(null);
        setSaving(true);
        try {
            await apiPatch(`/api/admin/staff/${member.id}/suspend`, {});
            setStaff(prev => prev.map(s => s.id === member.id ? { ...s, is_active: !s.is_active } : s));
            showMsg('success', `@${member.username} ${member.is_active ? 'suspended' : 'reactivated'}.`);
        } catch (e) { showMsg('error', `Error: ${e.message}`); } finally { setSaving(false); }
    };

    const handleEdit = async () => {
        if (!editing) return;
        setSaving(true);
        try {
            await apiPatch(`/api/admin/staff/${editing.id}`, {
                display_name: editing.display_name,
                role: editing.role,
                phone: editing.phone,
            });
            setStaff(prev => prev.map(s => s.id === editing.id
                ? { ...s, display_name: editing.display_name, role: editing.role, phone: editing.phone }
                : s
            ));
            setEditing(null);
            showMsg('success', 'Staff member updated.');
        } catch (e) { showMsg('error', `Error: ${e.message}`); } finally { setSaving(false); }
    };

    const handleReassign = async () => {
        if (!reassigning) return;
        setSaving(true);
        try {
            await apiPatch(`/api/admin/staff/${reassigning.id}/reassign`, { tenant_id: parseInt(reassigning.tenant_id) });
            await loadData();
            setReassigning(null);
            showMsg('success', 'Staff member reassigned.');
        } catch (e) { showMsg('error', `Error: ${e.message}`); } finally { setSaving(false); }
    };

    const handleCreate = async () => {
        if (!createForm.tenant_id) { showMsg('error', 'Select a tenant.'); return; }
        if (!createForm.username.trim()) { showMsg('error', 'Username is required.'); return; }
        if (!createForm.password) { showMsg('error', 'Password is required.'); return; }
        setSaving(true);
        try {
            await apiPost('/api/admin/staff', {
                tenant_id: parseInt(createForm.tenant_id),
                username: createForm.username.trim(),
                password: createForm.password,
                display_name: createForm.display_name.trim(),
                role: createForm.role,
                phone: createForm.phone.trim(),
            });
            await loadData();
            setCreating(false);
            setCreateForm(BLANK_CREATE);
            showMsg('success', `@${createForm.username} created successfully.`);
        } catch (e) { showMsg('error', e.message || 'Failed to create staff.'); } finally { setSaving(false); }
    };

    const mpList = mps.filter(m => !['admin', 'super_admin', 'sysadmin'].includes(m.role));

    return (
        <>
            {actionMsg.text && (
                <div className={`toast ${actionMsg.type === 'error' ? 'toast-error' : 'toast-success'}`}>
                    {actionMsg.text}
                </div>
            )}

            {suspendTarget && (
                <ConfirmModal
                    title={`${suspendTarget.is_active ? 'Suspend' : 'Reactivate'} @${suspendTarget.username}?`}
                    description={suspendTarget.is_active
                        ? `This will revoke @${suspendTarget.username}'s dashboard access until reactivated.`
                        : `This will restore @${suspendTarget.username}'s dashboard access.`}
                    confirmLabel={suspendTarget.is_active ? 'Suspend' : 'Reactivate'}
                    variant={suspendTarget.is_active ? 'danger' : 'warning'}
                    onConfirm={confirmSuspend}
                    onCancel={() => setSuspendTarget(null)}
                />
            )}

            {error && <div className="toast toast-error">{error}</div>}

            {/* Toolbar */}
            <div style={{ display: 'flex', gap: 10, marginBottom: '1rem', alignItems: 'center' }}>
                <div className="search-wrapper" style={{ flex: 1, maxWidth: 400 }}>
                    <svg className="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                    </svg>
                    <input type="text" className="form-input" placeholder="Search by name, username, or constituency…" value={search} onChange={e => setSearch(e.target.value)} />
                </div>
                <button className="btn-primary" style={{ fontSize: '0.8rem', padding: '7px 16px', flexShrink: 0 }}
                    onClick={() => { setCreateForm(BLANK_CREATE); setCreating(true); }}>
                    + Add Staff
                </button>
            </div>

            {loading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {[...Array(5)].map((_, i) => <div key={i} className="skeleton" style={{ height: 52, borderRadius: 8 }} />)}
                </div>
            ) : filtered.length === 0 ? (
                <div className="glass-panel">
                    <div className="empty-state">
                        <div className="empty-state-title">{search ? 'No results found' : 'No staff accounts found'}</div>
                        <div className="empty-state-desc">
                            {search ? `No staff match "${search}"` : 'Click "+ Add Staff" to create the first staff account'}
                        </div>
                    </div>
                </div>
            ) : (
                <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Staff Member</th>
                                <th>Account / Tenant</th>
                                <th>Role</th>
                                <th>WhatsApp (PA)</th>
                                <th>Status</th>
                                <th style={{ textAlign: 'right' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((s) => (
                                <tr key={s.id} style={{ opacity: s.is_active ? 1 : 0.55 }}>
                                    <td>
                                        <div style={{ fontWeight: 600, color: '#1a2e28' }}>{s.display_name || s.username}</div>
                                        <div style={{ fontSize: '0.72rem', color: '#6b7f76', marginTop: 1 }}>@{s.username}</div>
                                    </td>
                                    <td>
                                        <div style={{ color: '#1a2e28', fontSize: '0.82rem' }}>{s.tenant_name || '—'}</div>
                                        <div style={{ fontSize: '0.72rem', color: '#94a3a0' }}>{s.constituency || ''}</div>
                                    </td>
                                    <td>
                                        <span className={`badge ${ROLE_COLORS[s.role] || 'badge-slate'}`}>
                                            {s.role || 'user'}
                                        </span>
                                    </td>
                                    <td style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: s.phone ? '#1a2e28' : '#94a3a0' }}>
                                        {s.phone || '—'}
                                    </td>
                                    <td>
                                        <span className={`badge badge-dot ${s.is_active ? 'badge-green' : 'badge-red'}`}>
                                            {s.is_active ? 'Active' : 'Suspended'}
                                        </span>
                                    </td>
                                    <td style={{ textAlign: 'right' }}>
                                        <div style={{ display: 'flex', gap: 5, justifyContent: 'flex-end' }}>
                                            <button className="btn-ghost"
                                                onClick={() => setEditing({ id: s.id, display_name: s.display_name || '', role: s.role || 'staff', phone: s.phone || '' })}>
                                                Edit
                                            </button>
                                            <button className="btn-ghost" onClick={() => setReassigning({ id: s.id, tenant_id: s.tenant_id || '' })}>
                                                Reassign
                                            </button>
                                            <button
                                                onClick={() => handleSuspend(s)}
                                                disabled={saving}
                                                style={{
                                                    padding: '5px 10px', borderRadius: 6, border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                                                    background: s.is_active ? '#fff1f2' : '#ecfdf5',
                                                    color: s.is_active ? '#be123c' : '#065f46',
                                                    fontSize: '0.76rem', fontWeight: 600,
                                                }}
                                            >
                                                {s.is_active ? 'Suspend' : 'Reactivate'}
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Create Staff Modal */}
            {creating && (
                <div className="modal-overlay">
                    <div className="modal-card" style={{ maxWidth: 500, width: '100%' }}>
                        <h3 style={{ margin: '0 0 16px', fontSize: '1rem', fontWeight: 700 }}>Add Staff Member</h3>

                        <div className="form-row">
                            <label className="form-label">Account / Tenant *</label>
                            <select className="form-input" value={createForm.tenant_id}
                                onChange={e => setCreateForm(f => ({ ...f, tenant_id: e.target.value }))}>
                                <option value="">— select tenant —</option>
                                {mpList.map(m => (
                                    <option key={m.tenant_id} value={m.tenant_id}>
                                        {m.display_name} · {m.parliamentary_constituency} #{m.tenant_id}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                            <div className="form-row">
                                <label className="form-label">Username *</label>
                                <input className="form-input" placeholder="e.g. pa_ravi" value={createForm.username}
                                    onChange={e => setCreateForm(f => ({ ...f, username: e.target.value }))} />
                            </div>
                            <div className="form-row">
                                <label className="form-label">Display Name</label>
                                <input className="form-input" placeholder="Full name" value={createForm.display_name}
                                    onChange={e => setCreateForm(f => ({ ...f, display_name: e.target.value }))} />
                            </div>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                            <div className="form-row">
                                <label className="form-label">Password *</label>
                                <input className="form-input" type="password" placeholder="Min 8 characters" value={createForm.password}
                                    onChange={e => setCreateForm(f => ({ ...f, password: e.target.value }))} />
                            </div>
                            <div className="form-row">
                                <label className="form-label">Role</label>
                                <select className="form-input" value={createForm.role}
                                    onChange={e => setCreateForm(f => ({ ...f, role: e.target.value }))}>
                                    <option value="staff">staff</option>
                                    <option value="manager">manager</option>
                                    <option value="user">user</option>
                                </select>
                            </div>
                        </div>

                        <div className="form-row">
                            <label className="form-label">WhatsApp Number <span style={{ fontWeight: 400, color: '#94a3b8' }}>(for PA letter intake, optional)</span></label>
                            <input className="form-input" type="tel" placeholder="+919876543210"
                                value={createForm.phone} onChange={e => setCreateForm(f => ({ ...f, phone: e.target.value }))}
                                style={{ fontFamily: 'monospace' }} />
                            <div style={{ fontSize: '0.67rem', color: '#94a3a0', marginTop: 3 }}>
                                If set, this number can send letter photos and case queries on WhatsApp.
                            </div>
                        </div>

                        <div className="modal-footer">
                            <button className="btn-primary" onClick={handleCreate} disabled={saving}>
                                {saving ? 'Creating…' : 'Create Staff'}
                            </button>
                            <button className="btn-secondary" onClick={() => setCreating(false)} disabled={saving}>Cancel</button>
                        </div>
                    </div>
                </div>
            )}

            {/* Edit Modal */}
            {editing && (
                <div className="modal-overlay">
                    <div className="modal-card">
                        <h3 style={{ margin: '0 0 16px', fontSize: '1rem', fontWeight: 700 }}>Edit Staff Member</h3>
                        <div className="form-row">
                            <label className="form-label">Display Name</label>
                            <input className="form-input" value={editing.display_name}
                                onChange={e => setEditing(ed => ({ ...ed, display_name: e.target.value }))} />
                        </div>
                        <div className="form-row">
                            <label className="form-label">Role</label>
                            <select className="form-input" value={editing.role}
                                onChange={e => setEditing(ed => ({ ...ed, role: e.target.value }))}>
                                <option value="user">user</option>
                                <option value="staff">staff</option>
                                <option value="manager">manager</option>
                            </select>
                        </div>
                        <div className="form-row">
                            <label className="form-label">WhatsApp Number <span style={{ fontWeight: 400, color: '#94a3b8' }}>(PA intake, optional)</span></label>
                            <input className="form-input" type="tel" placeholder="+919876543210"
                                value={editing.phone || ''}
                                onChange={e => setEditing(ed => ({ ...ed, phone: e.target.value }))}
                                style={{ fontFamily: 'monospace' }} />
                        </div>
                        <div className="modal-footer">
                            <button className="btn-primary" onClick={handleEdit} disabled={saving}>
                                {saving ? 'Saving…' : 'Save Changes'}
                            </button>
                            <button className="btn-secondary" onClick={() => setEditing(null)}>Cancel</button>
                        </div>
                    </div>
                </div>
            )}

            {/* Reassign Modal */}
            {reassigning && (
                <div className="modal-overlay">
                    <div className="modal-card">
                        <h3 style={{ margin: '0 0 16px', fontSize: '1rem', fontWeight: 700 }}>Reassign to MP</h3>
                        <div className="form-row">
                            <label className="form-label">Select MP Tenant</label>
                            <select className="form-input" value={reassigning.tenant_id}
                                onChange={e => setReassigning(r => ({ ...r, tenant_id: e.target.value }))}>
                                <option value="">— select —</option>
                                {mpList.map(m => (
                                    <option key={m.tenant_id} value={m.tenant_id}>
                                        {m.display_name} · {m.parliamentary_constituency} #{m.tenant_id}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="modal-footer">
                            <button className="btn-primary" onClick={handleReassign} disabled={saving || !reassigning.tenant_id}>
                                {saving ? 'Saving…' : 'Reassign'}
                            </button>
                            <button className="btn-secondary" onClick={() => setReassigning(null)}>Cancel</button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
