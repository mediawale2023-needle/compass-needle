'use client';
import { useState, useEffect } from 'react';
import { apiGet, apiPatch } from '@/lib/api';

export default function StaffManagementPage() {
    const [staff, setStaff] = useState([]);
    const [mps, setMps] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [search, setSearch] = useState('');
    const [editing, setEditing] = useState(null); // { id, display_name, role }
    const [reassigning, setReassigning] = useState(null); // { id, tenant_id }
    const [saving, setSaving] = useState(false);
    const [actionMsg, setActionMsg] = useState('');

    useEffect(() => {
        Promise.all([
            apiGet('/api/admin/staff'),
            apiGet('/api/admin/mps'),
        ])
            .then(([s, m]) => {
                setStaff(s.staff || []);
                setMps(m.mps || []);
            })
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

    const showMsg = (msg) => {
        setActionMsg(msg);
        setTimeout(() => setActionMsg(''), 3000);
    };

    const handleSuspend = async (member) => {
        if (!confirm(`${member.is_active ? 'Suspend' : 'Reactivate'} @${member.username}?`)) return;
        setSaving(true);
        try {
            await apiPatch(`/api/admin/staff/${member.id}/suspend`, {});
            setStaff(prev => prev.map(s => s.id === member.id ? { ...s, is_active: !s.is_active } : s));
            showMsg(`@${member.username} ${member.is_active ? 'suspended' : 'reactivated'}.`);
        } catch (e) {
            showMsg(`Error: ${e.message}`);
        } finally {
            setSaving(false);
        }
    };

    const handleEdit = async () => {
        if (!editing) return;
        setSaving(true);
        try {
            await apiPatch(`/api/admin/staff/${editing.id}`, {
                display_name: editing.display_name,
                role: editing.role,
            });
            setStaff(prev => prev.map(s => s.id === editing.id
                ? { ...s, display_name: editing.display_name, role: editing.role }
                : s
            ));
            setEditing(null);
            showMsg('Staff member updated.');
        } catch (e) {
            showMsg(`Error: ${e.message}`);
        } finally {
            setSaving(false);
        }
    };

    const handleReassign = async () => {
        if (!reassigning) return;
        setSaving(true);
        try {
            await apiPatch(`/api/admin/staff/${reassigning.id}/reassign`, {
                tenant_id: parseInt(reassigning.tenant_id),
            });
            const mp = mps.find(m => m.tenant_id === parseInt(reassigning.tenant_id) || m.user_id === parseInt(reassigning.tenant_id));
            setStaff(prev => prev.map(s => s.id === reassigning.id
                ? { ...s, tenant_id: parseInt(reassigning.tenant_id), constituency: mp?.parliamentary_constituency || s.constituency }
                : s
            ));
            setReassigning(null);
            showMsg('Staff member reassigned.');
        } catch (e) {
            showMsg(`Error: ${e.message}`);
        } finally {
            setSaving(false);
        }
    };

    return (
        <>
            <div className="section-title">Staff Management</div>
            <p style={{ color: '#6b7f76', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
                Manage all non-admin staff accounts across tenants.
            </p>

            {actionMsg && (
                <div style={{ padding: '10px 16px', background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: 8, color: '#065f46', marginBottom: '1rem', fontSize: '0.85rem' }}>
                    {actionMsg}
                </div>
            )}

            {error && (
                <div style={{ padding: '10px 16px', background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: 8, color: '#be123c', marginBottom: '1rem', fontSize: '0.85rem' }}>
                    {error}
                </div>
            )}

            <div style={{ marginBottom: '1rem' }}>
                <input
                    type="text"
                    className="form-input"
                    placeholder="Search by name, username, or constituency…"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    style={{ width: '100%', maxWidth: 400 }}
                />
            </div>

            {loading ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: '#6b7f76' }}>Loading…</div>
            ) : filtered.length === 0 ? (
                <div className="glass-panel" style={{ textAlign: 'center', color: '#6b7f76', padding: '2rem' }}>
                    {search ? 'No staff match your search.' : 'No staff accounts found.'}
                </div>
            ) : (
                <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                        <thead>
                            <tr style={{ background: '#f0f7f4', borderBottom: '1px solid #e2ebe5' }}>
                                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#1a2e28' }}>Staff Member</th>
                                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#1a2e28' }}>Constituency</th>
                                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#1a2e28' }}>Role</th>
                                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#1a2e28' }}>Status</th>
                                <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#1a2e28' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((s, i) => (
                                <tr key={s.id} style={{ borderBottom: i < filtered.length - 1 ? '1px solid #e2ebe5' : 'none', opacity: s.is_active ? 1 : 0.6 }}>
                                    <td style={{ padding: '12px 16px' }}>
                                        <div style={{ fontWeight: 600, color: '#1a2e28' }}>{s.display_name || s.username}</div>
                                        <div style={{ fontSize: '0.75rem', color: '#6b7f76' }}>@{s.username}</div>
                                    </td>
                                    <td style={{ padding: '12px 16px', color: '#6b7f76' }}>{s.constituency || '—'}</td>
                                    <td style={{ padding: '12px 16px' }}>
                                        <span style={{
                                            padding: '2px 8px', borderRadius: 20,
                                            background: '#f0f7f4', color: '#006a4d',
                                            fontSize: '0.75rem', fontWeight: 600,
                                        }}>
                                            {s.role || 'user'}
                                        </span>
                                    </td>
                                    <td style={{ padding: '12px 16px' }}>
                                        <span style={{
                                            padding: '2px 8px', borderRadius: 20,
                                            background: s.is_active ? '#ecfdf5' : '#fff1f2',
                                            color: s.is_active ? '#065f46' : '#be123c',
                                            fontSize: '0.75rem', fontWeight: 600,
                                        }}>
                                            {s.is_active ? 'Active' : 'Suspended'}
                                        </span>
                                    </td>
                                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                                        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                                            <button
                                                onClick={() => setEditing({ id: s.id, display_name: s.display_name || '', role: s.role || 'user' })}
                                                style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid #e2ebe5', background: '#fff', color: '#1a2e28', fontSize: '0.75rem', cursor: 'pointer', fontFamily: 'inherit' }}
                                            >
                                                Edit
                                            </button>
                                            <button
                                                onClick={() => setReassigning({ id: s.id, tenant_id: s.tenant_id || '' })}
                                                style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid #e2ebe5', background: '#fff', color: '#1a2e28', fontSize: '0.75rem', cursor: 'pointer', fontFamily: 'inherit' }}
                                            >
                                                Reassign
                                            </button>
                                            <button
                                                onClick={() => handleSuspend(s)}
                                                disabled={saving}
                                                style={{
                                                    padding: '4px 10px', borderRadius: 6, border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                                                    background: s.is_active ? '#fff1f2' : '#ecfdf5',
                                                    color: s.is_active ? '#be123c' : '#065f46',
                                                    fontSize: '0.75rem', fontWeight: 600,
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
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ background: '#fff', borderRadius: 16, padding: '2rem', width: 400, boxShadow: '0 20px 60px rgba(0,0,0,0.15)' }}>
                        <h3 style={{ fontWeight: 700, color: '#1a2e28', marginBottom: '1.5rem' }}>Edit Staff Member</h3>
                        <div style={{ marginBottom: '1rem' }}>
                            <label style={{ fontSize: '0.8rem', color: '#6b7f76', fontWeight: 600, display: 'block', marginBottom: 4 }}>Display Name</label>
                            <input
                                className="form-input"
                                value={editing.display_name}
                                onChange={e => setEditing(ed => ({ ...ed, display_name: e.target.value }))}
                                style={{ width: '100%' }}
                            />
                        </div>
                        <div style={{ marginBottom: '1.5rem' }}>
                            <label style={{ fontSize: '0.8rem', color: '#6b7f76', fontWeight: 600, display: 'block', marginBottom: 4 }}>Role</label>
                            <select
                                className="form-input"
                                value={editing.role}
                                onChange={e => setEditing(ed => ({ ...ed, role: e.target.value }))}
                                style={{ width: '100%' }}
                            >
                                <option value="user">user</option>
                                <option value="staff">staff</option>
                                <option value="manager">manager</option>
                            </select>
                        </div>
                        <div style={{ display: 'flex', gap: 8 }}>
                            <button className="btn-primary" onClick={handleEdit} disabled={saving} style={{ flex: 1 }}>
                                {saving ? 'Saving…' : 'Save'}
                            </button>
                            <button onClick={() => setEditing(null)} style={{ flex: 1, padding: '8px 16px', borderRadius: 8, border: '1px solid #e2ebe5', background: '#fff', color: '#6b7f76', cursor: 'pointer', fontFamily: 'inherit' }}>
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Reassign Modal */}
            {reassigning && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ background: '#fff', borderRadius: 16, padding: '2rem', width: 400, boxShadow: '0 20px 60px rgba(0,0,0,0.15)' }}>
                        <h3 style={{ fontWeight: 700, color: '#1a2e28', marginBottom: '1.5rem' }}>Reassign to MP</h3>
                        <div style={{ marginBottom: '1.5rem' }}>
                            <label style={{ fontSize: '0.8rem', color: '#6b7f76', fontWeight: 600, display: 'block', marginBottom: 4 }}>Select MP Tenant</label>
                            <select
                                className="form-input"
                                value={reassigning.tenant_id}
                                onChange={e => setReassigning(r => ({ ...r, tenant_id: e.target.value }))}
                                style={{ width: '100%' }}
                            >
                                <option value="">— select —</option>
                                {mps.map(m => (
                                    <option key={m.tenant_id || m.user_id} value={m.tenant_id || m.user_id}>
                                        {m.display_name} · {m.parliamentary_constituency}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div style={{ display: 'flex', gap: 8 }}>
                            <button className="btn-primary" onClick={handleReassign} disabled={saving || !reassigning.tenant_id} style={{ flex: 1 }}>
                                {saving ? 'Saving…' : 'Reassign'}
                            </button>
                            <button onClick={() => setReassigning(null)} style={{ flex: 1, padding: '8px 16px', borderRadius: 8, border: '1px solid #e2ebe5', background: '#fff', color: '#6b7f76', cursor: 'pointer', fontFamily: 'inherit' }}>
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
