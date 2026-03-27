'use client';
import { useState, useEffect } from 'react';
import { apiGet, apiPatch } from '@/lib/api';
import ConfirmModal from '@/components/ConfirmModal';

export default function StaffManagementPage() {
    const [staff, setStaff] = useState([]);
    const [mps, setMps] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [search, setSearch] = useState('');
    const [editing, setEditing] = useState(null);
    const [reassigning, setReassigning] = useState(null);
    const [saving, setSaving] = useState(false);
    const [actionMsg, setActionMsg] = useState('');
    const [suspendTarget, setSuspendTarget] = useState(null);

    useEffect(() => {
        Promise.all([apiGet('/api/admin/staff'), apiGet('/api/admin/mps')])
            .then(([s, m]) => { setStaff(s.staff || []); setMps(m.mps || []); })
            .catch(e => setError(e.message || 'Failed to load'))
            .finally(() => setLoading(false));
    }, []);

    const filtered = search
        ? staff.filter(s =>
            (s.display_name || '').toLowerCase().includes(search.toLowerCase()) ||
            (s.username || '').toLowerCase().includes(search.toLowerCase()) ||
            (s.constituency || '').toLowerCase().includes(search.toLowerCase())
        )
        : staff;

    const showMsg = (msg) => { setActionMsg(msg); setTimeout(() => setActionMsg(''), 3500); };

    const handleSuspend = async (member) => {
        setSuspendTarget(member);
    };

    const confirmSuspend = async () => {
        if (!suspendTarget) return;
        const member = suspendTarget;
        setSuspendTarget(null);
        setSaving(true);
        try {
            await apiPatch(`/api/admin/staff/${member.id}/suspend`, {});
            setStaff(prev => prev.map(s => s.id === member.id ? { ...s, is_active: !s.is_active } : s));
            showMsg(`@${member.username} ${member.is_active ? 'suspended' : 'reactivated'}.`);
        } catch (e) { showMsg(`Error: ${e.message}`); } finally { setSaving(false); }
    };

    const handleEdit = async () => {
        if (!editing) return;
        setSaving(true);
        try {
            await apiPatch(`/api/admin/staff/${editing.id}`, { display_name: editing.display_name, role: editing.role });
            setStaff(prev => prev.map(s => s.id === editing.id ? { ...s, display_name: editing.display_name, role: editing.role } : s));
            setEditing(null);
            showMsg('Staff member updated.');
        } catch (e) { showMsg(`Error: ${e.message}`); } finally { setSaving(false); }
    };

    const handleReassign = async () => {
        if (!reassigning) return;
        setSaving(true);
        try {
            await apiPatch(`/api/admin/staff/${reassigning.id}/reassign`, { tenant_id: parseInt(reassigning.tenant_id) });
            const mp = mps.find(m => m.tenant_id === parseInt(reassigning.tenant_id) || m.user_id === parseInt(reassigning.tenant_id));
            setStaff(prev => prev.map(s => s.id === reassigning.id ? { ...s, tenant_id: parseInt(reassigning.tenant_id), constituency: mp?.parliamentary_constituency || s.constituency } : s));
            setReassigning(null);
            showMsg('Staff member reassigned.');
        } catch (e) { showMsg(`Error: ${e.message}`); } finally { setSaving(false); }
    };

    const ROLE_COLORS = { manager: 'badge-purple', staff: 'badge-blue', user: 'badge-slate' };

    return (
        <>
            {actionMsg && <div className="toast toast-success">{actionMsg}</div>}

            {/* Suspend/Reactivate Modal */}
            {suspendTarget && (
                <ConfirmModal
                    title={`${suspendTarget.is_active ? 'Suspend' : 'Reactivate'} @${suspendTarget.username}?`}
                    description={suspendTarget.is_active
                        ? `This will revoke @${suspendTarget.username}'s access to the MP dashboard. They will not be able to log in until reactivated.`
                        : `This will restore @${suspendTarget.username}'s access to the MP dashboard.`
                    }
                    confirmLabel={suspendTarget.is_active ? 'Suspend' : 'Reactivate'}
                    variant={suspendTarget.is_active ? 'danger' : 'warning'}
                    onConfirm={confirmSuspend}
                    onCancel={() => setSuspendTarget(null)}
                />
            )}
            {error && <div className="toast toast-error">{error}</div>}

            <div className="search-wrapper" style={{ marginBottom: '1rem', maxWidth: 400 }}>
                <svg className="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
                <input type="text" className="form-input" placeholder="Search by name, username, or constituency…" value={search} onChange={e => setSearch(e.target.value)} />
            </div>

            {loading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {[...Array(5)].map((_, i) => <div key={i} className="skeleton" style={{ height: 52, borderRadius: 8 }} />)}
                </div>
            ) : filtered.length === 0 ? (
                <div className="glass-panel">
                    <div className="empty-state">
                        <div className="empty-state-title">{search ? 'No results found' : 'No staff accounts found'}</div>
                        <div className="empty-state-desc">{search ? `No staff match "${search}"` : 'Staff accounts are created when MPs add users'}</div>
                    </div>
                </div>
            ) : (
                <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Staff Member</th>
                                <th>Constituency</th>
                                <th>Role</th>
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
                                    <td style={{ color: '#6b7f76' }}>{s.constituency || '—'}</td>
                                    <td>
                                        <span className={`badge ${ROLE_COLORS[s.role] || 'badge-slate'}`}>
                                            {s.role || 'user'}
                                        </span>
                                    </td>
                                    <td>
                                        <span className={`badge badge-dot ${s.is_active ? 'badge-green' : 'badge-red'}`}>
                                            {s.is_active ? 'Active' : 'Suspended'}
                                        </span>
                                    </td>
                                    <td style={{ textAlign: 'right' }}>
                                        <div style={{ display: 'flex', gap: 5, justifyContent: 'flex-end' }}>
                                            <button className="btn-ghost" onClick={() => setEditing({ id: s.id, display_name: s.display_name || '', role: s.role || 'user' })}>
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
                                                    fontSize: '0.76rem', fontWeight: 600, transition: 'opacity 0.15s',
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

            {/* Edit Modal */}
            {editing && (
                <div className="modal-overlay">
                    <div className="modal-card">
                        <h3>Edit Staff Member</h3>
                        <div className="form-row">
                            <label className="form-label">Display Name</label>
                            <input className="form-input" value={editing.display_name} onChange={e => setEditing(ed => ({ ...ed, display_name: e.target.value }))} />
                        </div>
                        <div className="form-row">
                            <label className="form-label">Role</label>
                            <select className="form-input" value={editing.role} onChange={e => setEditing(ed => ({ ...ed, role: e.target.value }))}>
                                <option value="user">user</option>
                                <option value="staff">staff</option>
                                <option value="manager">manager</option>
                            </select>
                        </div>
                        <div className="modal-footer">
                            <button className="btn-primary" onClick={handleEdit} disabled={saving}>{saving ? 'Saving…' : 'Save Changes'}</button>
                            <button className="btn-secondary" onClick={() => setEditing(null)}>Cancel</button>
                        </div>
                    </div>
                </div>
            )}

            {/* Reassign Modal */}
            {reassigning && (
                <div className="modal-overlay">
                    <div className="modal-card">
                        <h3>Reassign to MP</h3>
                        <div className="form-row">
                            <label className="form-label">Select MP Tenant</label>
                            <select className="form-input" value={reassigning.tenant_id} onChange={e => setReassigning(r => ({ ...r, tenant_id: e.target.value }))}>
                                <option value="">— select —</option>
                                {mps.map(m => (
                                    <option key={m.tenant_id || m.user_id} value={m.tenant_id || m.user_id}>
                                        {m.display_name} · {m.parliamentary_constituency}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="modal-footer">
                            <button className="btn-primary" onClick={handleReassign} disabled={saving || !reassigning.tenant_id}>{saving ? 'Saving…' : 'Reassign'}</button>
                            <button className="btn-secondary" onClick={() => setReassigning(null)}>Cancel</button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
